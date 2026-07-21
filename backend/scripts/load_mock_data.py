"""Load the Arabic mock dataset from scripts/mock_data.json into the dev database.

Run from backend/ with the venv active and the compose stack up:

    python scripts/load_mock_data.py            # aborts if data already present
    python scripts/load_mock_data.py --reset    # wipes the seeded tables first

All static content lives in scripts/mock_data.json — edit that file to change
the dataset: users (one per RBAC role, Egyptian names from forebears.io),
KB articles (written from real public Egyptian telecom sources; each row's
source_uri points at the page the facts came from), follow-up procedures,
customer reply phrases, chat transcripts with citation payloads, audit
events, and the name/governorate pools customers are drawn from.

This loader keeps only the generative glue:

- follow_up_tickets + call_logs: a 14-day window with Arabic transcripts
  assembled from the real greeting/reply scripts; the outcome mix comes from
  the JSON's call_plan_mix, tuned to land near the dashboard mock KPIs
  (FCR ≈ 0.87, completion ≈ 0.74, AHT ≈ 142s).
- fcr_reports: one report computed from the seeded call rows.
- kb_chunks: filled by running the real ingest pipeline against the TEI
  container when it is reachable; otherwise documents stay 'pending' for the
  nightly ingest task.
"""
import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")  # run as `python scripts/load_mock_data.py` from backend/

from app.data.db import SessionLocal  # noqa: E402
from app.data.models import (  # noqa: E402
    AuditLog,
    CallLog,
    ChatMessage,
    ChatSession,
    Customer,
    FCRReport,
    FollowUpTicket,
    KBDocument,
    User,
)
from app.speech.greeting import GreetingContext, greeting_text  # noqa: E402
from app.speech.replies import (  # noqa: E402
    OFFER_HELP_AR,
    RESOLVED_GOODBYE_AR,
    TRANSFER_AR,
    repeat_question_text,
)

DATA_PATH = Path(__file__).with_name("mock_data.json")
DATA = json.loads(DATA_PATH.read_text(encoding="utf-8"))

rng = random.Random(DATA["rng_seed"])  # deterministic so reseeding demos consistently

WINDOW_START = datetime.fromisoformat(DATA["window"]["start"])  # matches frontend mockReports trends
WINDOW_DAYS = DATA["window"]["days"]
CUSTOMER_POOLS = DATA["customers"]
REPLIES = DATA["customer_replies"]


def _hash_password(plain: str) -> str:
    """Hash with the real scheme so seeded users can log in via POST /api/auth/token."""
    from app.data.auth import hash_password

    return hash_password(plain)


def _phone() -> str:
    prefix = rng.choice(CUSTOMER_POOLS["phone_prefixes"])
    return prefix + "".join(str(rng.randint(0, 9)) for _ in range(8))


def _customer_name() -> str:
    return f"{rng.choice(CUSTOMER_POOLS['first_names'])} {rng.choice(CUSTOMER_POOLS['surnames'])}"


def _transcript(ctx: GreetingContext, turns: list[tuple[str, str]]) -> str:
    lines = [f"المساعد: {greeting_text(ctx)}"]
    for customer, assistant in turns:
        lines.append(f"العميل: {customer}")
        lines.append(f"المساعد: {assistant}")
    return "\n".join(lines)


def _seed_users(db) -> dict[str, User]:
    users = {}
    for i, entry in enumerate(DATA["users"]):
        user = User(
            username=entry["username"],
            email=entry["email"],
            full_name=entry["full_name"],
            hashed_password=_hash_password(DATA["default_password"]),
            role=entry["role"],
            is_active=True,
            # Staggered across the morning shift start so the roster looks lived-in.
            last_login_at=WINDOW_START
            + timedelta(days=WINDOW_DAYS - 1, hours=8, minutes=13 * i),
        )
        db.add(user)
        users[entry["username"]] = user
    db.flush()
    return users


def _seed_kb(db) -> list[KBDocument]:
    docs = []
    for entry in DATA["kb_documents"]:
        doc = KBDocument(
            title=entry["title"],
            source_uri=entry["source_uri"],
            content=entry["content"],
            mime_type="text/plain",
            source_checksum=hashlib.sha256(entry["content"].encode()).hexdigest(),
            ingestion_status="pending",
            metadata_={"seeded": True, "language": "ar"},
        )
        db.add(doc)
        docs.append(doc)
    db.flush()
    return docs


def _seed_customers(db) -> list[Customer]:
    customers = []
    phones = set()
    for i in range(CUSTOMER_POOLS["count"]):  # fewer customers than tickets — some repeat
        phone = _phone()
        while phone in phones:  # customer phones are unique
            phone = _phone()
        phones.add(phone)
        customer = Customer(
            name=_customer_name(),
            phone=phone,
            email=f"customer{i + 1:02d}@example.com" if rng.random() < 0.4 else None,
            governorate=rng.choice(CUSTOMER_POOLS["governorates"]),
            preferred_language="ar-EG" if rng.random() < 0.85 else "ar",
            crm_customer_id=f"CRM-CUST-{2000 + i}",
            created_at=WINDOW_START - timedelta(days=rng.randint(30, 400)),
        )
        db.add(customer)
        customers.append(customer)
    db.flush()
    return customers


def _seed_calls(db, customers: list[Customer]) -> tuple[list[FollowUpTicket], list[CallLog]]:
    tickets, calls = [], []
    procedures = DATA["procedures"]
    plans = [plan for plan, count in DATA["call_plan_mix"].items() for _ in range(count)]
    rng.shuffle(plans)

    for i, plan in enumerate(plans):
        entry = procedures[i % len(procedures)]
        created = WINDOW_START + timedelta(
            days=i % WINDOW_DAYS, hours=rng.randint(9, 17), minutes=rng.randint(0, 59)
        )
        # Every customer gets one ticket; the surplus tickets are repeat callers.
        customer = customers[i] if i < len(customers) else rng.choice(customers)
        ticket = FollowUpTicket(
            crm_ticket_id=f"CRM-2026-{1000 + i}",
            customer_id=customer.id,
            customer_name=customer.name,
            customer_phone=customer.phone,
            procedure=entry["procedure"],
            issue_summary=entry["issue_summary"],
            inbound_call_at=created - timedelta(days=1),
            follow_up_status={
                "resolved_first": "resolved",
                "resolved_retry": "resolved",
                "transferred": "escalated",
                "unresolved": "in_progress",
                "queued": "queued",
            }[plan],
            created_at=created,
            updated_at=created,
        )
        db.add(ticket)
        db.flush()
        tickets.append(ticket)

        ctx = GreetingContext(
            customer_name=ticket.customer_name,
            ticket_id=ticket.crm_ticket_id,
            procedure=ticket.procedure,
        )
        started = created + timedelta(hours=rng.randint(1, 4))

        def _call(**overrides) -> CallLog:
            base = dict(
                customer_phone=ticket.customer_phone,
                ticket_id=ticket.crm_ticket_id,
                status="completed",
                attempt_number=1,
                attempts=1,
                created_at=started,
                updated_at=started,
                started_at=started,
            )
            base.update(overrides)
            row = CallLog(**base)
            db.add(row)
            db.flush()
            row.provider_call_sid = f"CA{hashlib.md5(str(row.id).encode()).hexdigest()}"
            calls.append(row)
            return row

        if plan == "queued":
            _call(status="queued", started_at=None, provider_call_sid=None, attempts=0)
            continue

        if plan == "resolved_first":
            duration = max(60, int(rng.gauss(138, 25)))
            _call(
                outcome="resolved",
                duration_seconds=duration,
                completed_at=started + timedelta(seconds=duration),
                transcript=_transcript(
                    ctx, [(rng.choice(REPLIES["yes"]), RESOLVED_GOODBYE_AR)]
                ),
            )
        elif plan == "resolved_retry":
            first = _call(status="no_answer", failure_reason="no-answer")
            retry_started = started + timedelta(hours=3)
            duration = max(60, int(rng.gauss(150, 25)))
            _call(
                parent_call_log_id=first.id,
                attempt_number=2,
                attempts=2,
                created_at=retry_started,
                started_at=retry_started,
                outcome="resolved",
                duration_seconds=duration,
                completed_at=retry_started + timedelta(seconds=duration),
                transcript=_transcript(
                    ctx, [(rng.choice(REPLIES["yes"]), RESOLVED_GOODBYE_AR)]
                ),
            )
        elif plan == "transferred":
            duration = max(90, int(rng.gauss(175, 30)))
            _call(
                outcome="transferred",
                duration_seconds=duration,
                completed_at=started + timedelta(seconds=duration),
                transcript=_transcript(ctx, [(rng.choice(REPLIES["agent"]), TRANSFER_AR)]),
            )
        else:  # unresolved
            duration = max(90, int(rng.gauss(190, 30)))
            _call(
                outcome="unresolved",
                duration_seconds=duration,
                completed_at=started + timedelta(seconds=duration),
                transcript=_transcript(
                    ctx,
                    [
                        (rng.choice(REPLIES["uncertain"]), repeat_question_text(ctx)),
                        (rng.choice(REPLIES["no"]), OFFER_HELP_AR),
                    ],
                ),
            )
    return tickets, calls


def _seed_chat(db, users: dict[str, User], docs: list[KBDocument]) -> None:
    for day_offset, convo in enumerate(DATA["chat_conversations"]):
        opened = WINDOW_START + timedelta(days=10 + day_offset, hours=11)
        session = ChatSession(
            user=users[convo["username"]], created_at=opened, updated_at=opened
        )
        db.add(session)
        db.flush()
        at = opened
        for qa in convo["qa"]:
            db.add(
                ChatMessage(
                    session_id=session.id, role="user", content=qa["question"],
                    sources=[], created_at=at,
                )
            )
            at += timedelta(seconds=2)
            sources = [
                {
                    "document_id": docs[cite["doc_index"]].id,
                    "title": docs[cite["doc_index"]].title,
                    "snippet": cite["snippet"],
                }
                for cite in qa["citations"]
            ]
            db.add(
                ChatMessage(
                    session_id=session.id, role="assistant", content=qa["answer"],
                    sources=sources, latency_ms=rng.randint(700, 1900), created_at=at,
                )
            )
            at += timedelta(minutes=rng.randint(1, 5))


def _seed_report(db, users: dict[str, User], calls: list[CallLog]) -> None:
    completed = [c for c in calls if c.outcome is not None]
    first_attempt_resolved = [
        c for c in completed if c.outcome == "resolved" and c.attempt_number == 1
    ]
    resolved_or_final = [c for c in completed if c.attempt_number == 1]
    without_human = [c for c in completed if c.outcome in ("resolved", "unresolved")]
    durations = [c.duration_seconds for c in completed if c.duration_seconds]

    fcr = len(first_attempt_resolved) / len(resolved_or_final)
    completion = len(without_human) / len(completed)
    aht = sum(durations) / len(durations)
    period_end = WINDOW_START + timedelta(days=WINDOW_DAYS)

    lines = [
        "# تقرير الحلول من المكالمة الأولى (FCR)",
        f"الفترة: من {WINDOW_START:%Y-%m-%d} إلى {period_end:%Y-%m-%d}",
        "",
        f"- إجمالي مكالمات المتابعة: {len(completed)}",
        f"- تم الحل من أول مكالمة: {len(first_attempt_resolved)} "
        f"(نسبة {fcr:.0%})",
        f"- نسبة الإتمام الآلي بدون تدخل بشري: {completion:.0%}",
        f"- متوسط مدة المكالمة: {aht:.0f} ثانية",
        "",
        "أُعد هذا التقرير آليًا لفريق الجودة من واقع سجل المكالمات.",
    ]
    db.add(
        FCRReport(
            period_start=WINDOW_START,
            period_end=period_end,
            total_calls=len(completed),
            resolved_first_attempt=len(first_attempt_resolved),
            fcr_rate=round(fcr, 4),
            completion_rate=round(completion, 4),
            average_handle_time_seconds=round(aht, 1),
            report_markdown="\n".join(lines),
            generated_by_user_id=users["hala.elshazly"].id,
        )
    )


def _seed_audit(db, users: dict[str, User], docs: list[KBDocument]) -> None:
    for i, event in enumerate(DATA["audit_events"]):
        if "doc_index" in event:
            resource_id = str(docs[event["doc_index"]].id)
        else:
            resource_id = event.get("resource_id")
        db.add(
            AuditLog(
                user_id=users[event["username"]].id,
                action=event["action"],
                resource_type=event["resource_type"],
                resource_id=resource_id,
                detail={"seeded": True},
                created_at=WINDOW_START + timedelta(days=10, hours=9, minutes=7 * i),
            )
        )


def _embed_kb(docs: list[KBDocument]) -> None:
    """Run the real ingest pipeline so kb_chunks gets actual TEI embeddings."""
    from app.conversation.rag import ingest

    for doc in docs:
        try:
            chunks = ingest.ingest_document(doc.id)
            print(f"  embedded '{doc.title}' → {chunks} chunk(s)")
        except Exception as exc:  # TEI container down — nightly task will retry
            print(f"  ! could not embed '{doc.title}' ({exc}); left as 'pending'")


SEEDED_TABLES = [
    AuditLog, ChatMessage, ChatSession, FCRReport, CallLog, FollowUpTicket, Customer, User,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--reset", action="store_true",
        help="delete existing rows in the seeded tables first (dev only)",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reset:
            from sqlalchemy import text

            from app.data.models import KBChunk

            tables = [m.__tablename__ for m in [*SEEDED_TABLES, KBChunk, KBDocument]]
            if db.get_bind().dialect.name == "postgresql":
                # RESTART IDENTITY keeps seeded ids stable (users start at 1)
                # across reseeds; plain DELETE leaves the sequences advanced.
                db.execute(
                    text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")
                )
                print(f"reset: truncated {', '.join(tables)}")
            else:
                for model in [*SEEDED_TABLES, KBChunk, KBDocument]:
                    deleted = db.query(model).delete()
                    if deleted:
                        print(f"reset: removed {deleted} row(s) from {model.__tablename__}")
            db.commit()
        elif any(db.query(m.id).first() for m in [*SEEDED_TABLES, KBDocument]):
            print("Database already has data — rerun with --reset to reseed.")
            return 1

        users = _seed_users(db)
        customers = _seed_customers(db)
        docs = _seed_kb(db)
        _tickets, calls = _seed_calls(db, customers)
        _seed_chat(db, users, docs)
        _seed_report(db, users, calls)
        _seed_audit(db, users, docs)
        db.commit()
        doc_ids = [d.id for d in docs]
        print(
            f"seeded from {DATA_PATH.name}: {len(users)} users, {len(customers)} customers, "
            f"{len(docs)} kb docs, {len(_tickets)} tickets, {len(calls)} call logs, "
            "chat history, 1 FCR report, audit trail"
        )
        print("\nuser roster:")
        for user in users.values():
            print(f"  id={user.id:<3} {user.username:<20} {user.role:<16} {user.full_name}")
        print("\ncustomer sample (first 8):")
        for customer in customers[:8]:
            print(
                f"  id={customer.id:<3} {customer.phone:<15} "
                f"{customer.governorate:<12} {customer.name}"
            )

    print("embedding KB documents via the TEI container:")
    with SessionLocal() as db:
        _embed_kb([db.get(KBDocument, i) for i in doc_ids])
    return 0


if __name__ == "__main__":
    sys.exit(main())
