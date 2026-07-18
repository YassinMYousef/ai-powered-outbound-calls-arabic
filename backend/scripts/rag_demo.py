"""End-to-end RAG demo CLI — exercises the real product loop over HTTP.

    upload (/api/kb/documents) → Celery ingest (chunk → TEI embed → pgvector)
    → /api/chat/query → retrieve top-K → Claude answer with citations.

Prerequisites (see the run-stack skill): docker compose infra, uvicorn on :8000,
and the Celery worker (uploads are embedded by the worker, not the API process).

Usage (from backend/, venv active):
    python scripts/rag_demo.py                       # seed sample KB docs, then ask interactively
    python scripts/rag_demo.py --ask "كيف أستبدل الشريحة؟"   # one-shot question
    python scripts/rag_demo.py --file ../docs/faq.md         # also upload your own document
"""
import argparse
import sys
import time

import httpx

DEFAULT_API = "http://localhost:8000"
EMBED_TIMEOUT_S = 60

# Small in-domain KB (MSA) so the demo works on an empty database. Three distinct
# topics so retrieval has real ranking work to do.
SAMPLE_DOCS = {
    "sim_replacement.md": """\
# إجراءات استبدال شريحة الهاتف (SIM)

لاستبدال شريحة تالفة أو مفقودة، يجب على العميل التوجه إلى أقرب فرع ومعه بطاقة
الرقم القومي الأصلية. يتم التحقق من أن الخط مسجل باسم العميل نفسه، ثم تصدر
شريحة جديدة بنفس الرقم خلال خمس عشرة دقيقة.

رسوم استبدال الشريحة خمسون جنيهًا تُضاف إلى الفاتورة التالية، وتُعفى الحالات
الناتجة عن عيب مصنعي من الرسوم. في حالة السرقة يجب تقديم رقم محضر الشرطة
لإيقاف الخط القديم فورًا قبل إصدار الشريحة البديلة.
""",
    "router_troubleshooting.md": """\
# خطوات معالجة انقطاع خدمة الإنترنت المنزلي

عند شكوى العميل من انقطاع الإنترنت، اطلب منه أولًا إعادة تشغيل الراوتر بفصل
الكهرباء لمدة ثلاثين ثانية ثم إعادة توصيله والانتظار دقيقتين حتى تستقر الأضواء.
إذا ظل ضوء DSL يرمش، تحقق من توصيل سلك الهاتف في مقسم الإشارة (السبليتر).

إذا لم تُحل المشكلة بعد إعادة التشغيل، افتح بلاغًا فنيًا في النظام وأبلغ العميل
بأن مدة معالجة البلاغ الفني ثمانٍ وأربعون ساعة كحد أقصى، مع متابعة هاتفية
بعد إغلاق البلاغ للتأكد من عودة الخدمة.
""",
    "refund_policy.md": """\
# سياسة استرداد المبالغ المدفوعة

يحق للعميل استرداد قيمة أي خدمة مدفوعة خلال أربعة عشر يومًا من تاريخ التفعيل
بشرط عدم استهلاك أكثر من عشرين بالمئة من باقتها. يُقدَّم طلب الاسترداد عبر خدمة
العملاء ويُرد المبلغ بنفس وسيلة الدفع الأصلية خلال سبعة أيام عمل.

لا تسري سياسة الاسترداد على رسوم التركيبات والأجهزة بعد تركيبها، ولا على
الباقات الترويجية المخفضة. في حالة الخصم الخاطئ يُرد المبلغ كاملًا فورًا دون
التقيد بمدة الأربعة عشر يومًا.
""",
}


def _fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_health(client: httpx.Client) -> None:
    try:
        response = client.get("/health")
        response.raise_for_status()
    except httpx.HTTPError as exc:
        _fail(f"API is not reachable ({exc}) — start the stack first (run-stack skill)")


def existing_titles(client: httpx.Client) -> dict[str, dict]:
    response = client.get("/api/kb/documents")
    response.raise_for_status()
    return {doc["title"]: doc for doc in response.json()}


def upload_doc(client: httpx.Client, filename: str, content: bytes) -> int:
    response = client.post(
        "/api/kb/documents",
        files={"file": (filename, content, "text/markdown")},
    )
    if response.status_code != 202:
        _fail(f"upload of {filename} failed ({response.status_code}): {response.text[:200]}")
    doc = response.json()
    print(f"  uploaded {filename} -> doc id {doc['id']}")
    return doc["id"]


def wait_embedded(client: httpx.Client, doc_ids: set[int]) -> None:
    """Poll until the Celery worker stamps embedded_at on every uploaded doc."""
    if not doc_ids:
        return
    print(f"waiting for embedding of {len(doc_ids)} document(s) (Celery worker + TEI)...")
    deadline = time.monotonic() + EMBED_TIMEOUT_S
    pending = set(doc_ids)
    while pending:
        if time.monotonic() > deadline:
            _fail(
                f"docs {sorted(pending)} were not embedded within {EMBED_TIMEOUT_S}s — "
                "is the Celery worker running? "
                "(celery -A app.workers.celery_app worker --loglevel=info)"
            )
        time.sleep(1.5)
        response = client.get("/api/kb/documents")
        response.raise_for_status()
        for doc in response.json():
            if doc["id"] in pending and doc["embedded_at"]:
                print(f"  embedded: {doc['title']} (doc id {doc['id']})")
                pending.discard(doc["id"])


def seed_kb(client: httpx.Client, include_samples: bool, extra_files: list[str]) -> None:
    known = existing_titles(client)
    uploaded: set[int] = set()
    if include_samples:
        for filename, text in SAMPLE_DOCS.items():
            title = filename.rsplit(".", 1)[0]
            if title in known and known[title]["embedded_at"]:
                print(f"  already embedded: {title} (doc id {known[title]['id']})")
                continue
            uploaded.add(upload_doc(client, filename, text.encode("utf-8")))
    for path in extra_files:
        try:
            with open(path, "rb") as handle:
                content = handle.read()
        except OSError as exc:
            _fail(f"cannot read {path}: {exc}")
        uploaded.add(upload_doc(client, path.rsplit("/", 1)[-1], content))
    wait_embedded(client, uploaded)


def ask(client: httpx.Client, question: str, top_k: int | None) -> None:
    payload: dict = {"query": question}
    if top_k:
        payload["top_k"] = top_k
    started = time.monotonic()
    response = client.post("/api/chat/query", json=payload)
    elapsed = time.monotonic() - started
    if response.status_code != 200:
        _fail(f"query failed ({response.status_code}): {response.text[:300]}")
    result = response.json()

    print(f"\nanswer ({elapsed:.1f}s):\n  {result['answer']}\n")
    if not result["sources"]:
        print("sources: none — the KB does not cover this question\n")
        return
    print("sources:")
    for source in result["sources"]:
        print(
            f"  - {source['title']} (doc {source['doc_id']}, chunk {source['chunk_index']}, "
            f"score {source['score']:.3f})"
        )
        for quote in source["quotes"]:
            print(f'      "{quote.strip()}"')
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="End-to-end RAG demo over the real API.")
    parser.add_argument("--api", default=DEFAULT_API, help=f"API base URL (default {DEFAULT_API})")
    parser.add_argument("--ask", help="one-shot Arabic question (otherwise: interactive prompt)")
    parser.add_argument(
        "--file", action="append", default=[], help="extra document to upload (repeatable)"
    )
    parser.add_argument("--top-k", type=int, default=None, help="passages to retrieve")
    parser.add_argument(
        "--skip-seed", action="store_true", help="do not upload the built-in sample docs"
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.api, timeout=90.0) as client:
        check_health(client)
        if not args.skip_seed or args.file:
            print("seeding knowledge base:")
            seed_kb(client, include_samples=not args.skip_seed, extra_files=args.file)

        if args.ask:
            ask(client, args.ask, args.top_k)
            return

        print("اكتب سؤالك بالعربية (Ctrl-D للخروج):")
        while True:
            try:
                question = input("؟ ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if question:
                ask(client, question, args.top_k)


if __name__ == "__main__":
    main()
