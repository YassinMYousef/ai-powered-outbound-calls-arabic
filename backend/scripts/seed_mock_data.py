"""Seed the dev database with realistic Arabic mock data across every table.

Run from backend/ with the venv active and the compose stack up:

    python scripts/seed_mock_data.py            # aborts if data already present
    python scripts/seed_mock_data.py --reset    # wipes the seeded tables first

What gets seeded and where the content comes from:

- kb_documents: Arabic knowledge-base articles written from real, public
  Egyptian telecom sources (each row's source_uri points at the page the facts
  came from): Vodafone Egypt service codes (web.vodafone.com.eg), the NTRA
  complaint procedure (complaints.tra.gov.eg), WE home-internet triage
  (te.eg), and mobile number portability (gate.ahram.org.eg), plus one
  internal SOP for the outbound follow-up flow.
- kb_chunks: filled by running the real ingest pipeline against the TEI
  container when it is reachable; otherwise documents stay 'pending' for the
  nightly ingest task.
- users: Egyptian-named staff for each RBAC role (names drawn from
  forebears.io's most-common Egyptian forename/surname lists). Password for
  every seeded user is 'changeme123' (pbkdf2 placeholder until auth.py lands).
- follow_up_tickets + call_logs: a 14-day window (2026-07-05 → 2026-07-18)
  matching the dashboard's mock trend range, with Arabic transcripts assembled
  from the real greeting/reply scripts and dialog.py's intent phrase tables.
  Outcome mix is tuned to land near the dashboard mock KPIs
  (FCR ≈ 0.87, completion ≈ 0.74, AHT ≈ 142s).
- chat_sessions/chat_messages: agent Q&A over the seeded KB articles, with
  the citation payload pointing at the seeded document ids.
- fcr_reports: one report computed from the seeded call rows.
- audit_logs: representative kb.read / chat.query / report.view entries.
"""
import argparse
import hashlib
import random
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, ".")  # run as `python scripts/seed_mock_data.py` from backend/

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

rng = random.Random(20260719)  # deterministic so reseeding demos consistently

WINDOW_START = datetime(2026, 7, 5, tzinfo=UTC)  # matches frontend mockReports trends
WINDOW_DAYS = 14

# --- users ----------------------------------------------------------------
# Names assembled from forebears.io/egypt/forenames + /surnames (most common
# Egyptian given names and family names), written in Arabic script.

SEED_USERS = [
    ("admin", "admin@callcenter.local", "أحمد عبد الفتاح", "admin"),
    ("sara.elmasry", "sara.elmasry@callcenter.local", "سارة المصري", "agent"),
    ("karim.hussein", "karim.hussein@callcenter.local", "كريم حسين", "agent"),
    ("mona.ibrahim", "mona.ibrahim@callcenter.local", "منى إبراهيم", "agent"),
    ("youssef.elsayed", "youssef.elsayed@callcenter.local", "يوسف السيد", "agent"),
    ("mahmoud.ramadan", "mahmoud.ramadan@callcenter.local", "محمود رمضان", "agent"),
    ("yasmin.ali", "yasmin.ali@callcenter.local", "ياسمين علي", "agent"),
    ("amr.hassan", "amr.hassan@callcenter.local", "عمرو حسن", "agent"),
    ("dina.saeed", "dina.saeed@callcenter.local", "دينا سعيد", "agent"),
    ("mostafa.khalil", "mostafa.khalil@callcenter.local", "مصطفى خليل", "agent"),
    ("heba.abdelrahman", "heba.abdelrahman@callcenter.local", "هبة عبد الرحمن", "agent"),
    ("hala.elshazly", "hala.elshazly@callcenter.local", "هالة الشاذلي", "quality_manager"),
    ("tarek.fathy", "tarek.fathy@callcenter.local", "طارق فتحي", "quality_manager"),
]

FIRST_NAMES = [
    "أحمد", "محمد", "محمود", "مصطفى", "يوسف", "عمر", "خالد", "طارق", "عمرو", "هاني",
    "كريم", "إسلام", "فاطمة", "آية", "مريم", "نور", "سلمى", "منى", "هبة", "ياسمين",
    "شيماء", "دينا",
]
SURNAMES = [
    "السيد", "حسن", "المصري", "عبد الرحمن", "حسين", "إبراهيم", "علي", "الشاذلي",
    "فتحي", "عبد الفتاح", "رمضان", "سعيد",
]
GOVERNORATES = [
    "القاهرة", "الجيزة", "الإسكندرية", "الدقهلية", "الشرقية", "القليوبية",
    "المنوفية", "أسيوط", "سوهاج", "أسوان", "بورسعيد", "السويس",
]
N_CUSTOMERS = 32  # fewer customers than tickets — some are repeat callers


def _hash_password(plain: str) -> str:
    """pbkdf2 placeholder until data/auth.py picks the real scheme."""
    salt = "callcenter-seed"
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 260_000).hex()
    return f"pbkdf2_sha256$260000${salt}${digest}"


# --- knowledge base -------------------------------------------------------

KB_DOCS = [
    {
        "title": "أرقام وأكواد خدمة عملاء فودافون مصر",
        "source_uri": "https://web.vodafone.com.eg/ar/call-us",
        "content": (
            "للتواصل مع خدمة عملاء فودافون مصر: اتصل بالرقم 888 من أي خط فودافون، "
            "أو 16888 من أي شبكة أخرى، أو 00201001888888 من خارج مصر.\n\n"
            "خدمة عملاء فودافون كاش على الرقم 7001، وعملاء فودافون ريد على الرقم 1100، "
            "وخدمة عملاء الأعمال على الرقم 247. يمكن أيضًا التواصل مجانًا عبر واتساب "
            "على الرقم 01050888888.\n\n"
            "لمعرفة كود الـ PUK الخاص بالشريحة اطلب ‎*888*رقم الخط#‎ من أي رقم آخر. "
            "لتفعيل خدمة التجوال الدولي لخطوط الكارت اطلب الكود ‎*888*5#‎ ولإلغائها "
            "‎*888*51#‎، أما خطوط الفاتورة فيلزم الاتصال بخدمة العملاء على 888.\n\n"
            "إذا توقفت الشريحة عن العمل وكانت شريحة أخرى تعمل جيدًا في نفس المكان، "
            "يُنصح بزيارة أقرب فرع فودافون لاستبدال الشريحة لأنها قد تكون تالفة."
        ),
    },
    {
        "title": "خطوات تقديم شكوى للجهاز القومي لتنظيم الاتصالات (NTRA)",
        "source_uri": "https://complaints.tra.gov.eg/",
        "content": (
            "يتلقى الجهاز القومي لتنظيم الاتصالات شكاوى مستخدمي خدمات الاتصالات في مصر "
            "عبر الرقم المختصر 155 يوميًا من 8 صباحًا حتى 10 مساءً، أو عبر تطبيق "
            "My NTRA، أو منصة تلقي الشكاوى الإلكترونية، أو البريد الإلكتروني "
            "complaints@tra.gov.eg.\n\n"
            "شروط قبول الشكوى: يجب أولًا تقديم الشكوى إلى الشركة المشكو في حقها، "
            "وفي حالة عدم حلها خلال 48 ساعة يمكن تصعيدها للجهاز مع ذكر رقم الشكوى "
            "المسجل لدى الشركة. يجب أن يكون الرقم المشكو منه مملوكًا لمقدم الشكوى، "
            "وفي حالة التقديم نيابة عن الغير يلزم تفويض كتابي.\n\n"
            "أنواع الشكاوى التي يختص بها الجهاز: توصيل وتغطية شبكات الاتصالات، "
            "خدمات الإنترنت، تأخير إصلاح الأعطال، الفواتير وطرق محاسبة خدمات "
            "الاتصالات، توصيل خدمات الاتصالات، وأجهزة التليفون المحمول."
        ),
    },
    {
        "title": "أعطال الإنترنت المنزلي WE — خطوات الفحص قبل تصعيد الشكوى",
        "source_uri": "https://www.te.eg/personal/services/fixed-broadband",
        "content": (
            "للإبلاغ عن أعطال الإنترنت المنزلي أو التليفون الأرضي من الشركة المصرية "
            "للاتصالات WE: اتصل بمركز خدمة العملاء على الرقم المختصر 111 أو الرقم "
            "19777، أو من المحمول على 01555000111.\n\n"
            "قبل تسجيل الشكوى جرّب الخطوات الآتية:\n"
            "1. أعد تشغيل الراوتر بفصل الكهرباء عنه لمدة دقيقة كاملة ثم إعادة توصيله، "
            "فهذا يعيد تهيئة الشبكة ويحل معظم الأعطال المؤقتة.\n"
            "2. تأكد من عدم وجود أجهزة تستهلك الباقة في الخلفية، ومن أن باقة "
            "الإنترنت لم تنفد.\n"
            "3. جرّب زر WPS لإعادة اتصال الأجهزة بالشبكة بشكل أسرع.\n"
            "4. إذا استمر العطل بعد هذه الخطوات، سجّل الشكوى وسيصلك رقم متابعة، "
            "ويتم إصلاح معظم الأعطال خلال 48 ساعة."
        ),
    },
    {
        "title": "نقل الرقم بين شبكات المحمول بنفس الرقم (MNP)",
        "source_uri": "https://gate.ahram.org.eg/News/2426030.aspx",
        "content": (
            "تتيح خدمة نقل الأرقام (MNP) الانتقال من شركة محمول إلى أخرى مع الاحتفاظ "
            "بنفس الرقم خلال 24 ساعة وبشكل مجاني، لعملاء الكارت والفاتورة.\n\n"
            "الخطوات: التوجه إلى أقرب فرع للشركة المراد الانتقال إليها، وتقديم طلب "
            "النقل مع بطاقة الرقم القومي سارية (أو جواز السفر للأجانب)، واستلام شريحة "
            "جديدة غير مفعّلة. خلال يوم عمل واحد تصل رسالة نصية بقبول الطلب، وعندها "
            "تُستبدل الشريحة القديمة بالجديدة ويُفعَّل الرقم على الشبكة الجديدة.\n\n"
            "الشروط: أن يكون مقدم الطلب هو المالك الفعلي للرقم، وأن يكون قد مضى على "
            "تشغيل الخط 4 أشهر على الأقل، وألا توجد مديونيات مستحقة على الخط."
        ),
    },
    {
        "title": "سياسة مكالمات المتابعة الآلية — إجراءات داخلية",
        "source_uri": None,
        "content": (
            "مستند داخلي: يتصل النظام الآلي بالعميل للتأكد من إتمام الإجراء الذي "
            "نوقش في مكالمته الواردة السابقة.\n\n"
            "سيناريو المكالمة: يبدأ المساعد بالتحية وذكر رقم الطلب ثم يسأل: هل "
            "تمكّنت من إتمام الإجراء؟ إذا أجاب العميل بنعم تُسجَّل الحالة «تم الحل» "
            "وتُنهى المكالمة بالشكر. إذا أجاب بلا يُعرض عليه مزيد من المساعدة، وعند "
            "تكرار الرفض يُحوَّل إلى ممثل خدمة عملاء بشري. إذا كان غير متأكد يُعاد "
            "السؤال ثم يُعرض عليه المساعدة. طلب العميل التحدث مع موظف يُنفَّذ فورًا "
            "في أي مرحلة.\n\n"
            "سياسة إعادة المحاولة: في حالة عدم الرد أو انشغال الخط يُعاد الاتصال "
            "بحد أقصى محاولتين إضافيتين في أوقات مختلفة من اليوم، وتُسجَّل كل "
            "محاولة في سجل المكالمات باستقلال."
        ),
    },
]

# --- follow-up tickets and calls ------------------------------------------
# Each procedure is verb-phrased Arabic because it feeds
# speech/greeting.GreetingContext.procedure ("هل تمكّنت من {procedure}؟").

PROCEDURES = [
    ("إعادة تشغيل الراوتر بفصل الكهرباء عنه لمدة دقيقة", "عطل متكرر في الإنترنت المنزلي"),
    ("زيارة أقرب فرع لاستبدال الشريحة التالفة", "الشريحة لا تلتقط الشبكة"),
    ("تفعيل خدمة التجوال الدولي من الكود ‎*888*5#‎", "سفر قريب ويحتاج تفعيل التجوال"),
    ("تقديم طلب نقل الرقم مع بطاقة الرقم القومي في فرع الشركة الجديدة", "يرغب في نقل رقمه لشبكة أخرى"),
    ("تسجيل شكوى الفاتورة لدى الشركة وانتظار 48 ساعة قبل التصعيد للجهاز", "اعتراض على قيمة الفاتورة"),
    ("شحن الرصيد وتفعيل الباقة الجديدة من التطبيق", "الباقة نفدت قبل نهاية الشهر"),
    ("إدخال كود الـ PUK المرسل لفتح الشريحة", "الشريحة مقفولة بعد إدخال رقم سري خاطئ"),
    ("متابعة رقم الشكوى المسجل لدى الدعم الفني للخط الأرضي", "بطء شديد في سرعة الإنترنت"),
]

YES_REPLIES = ["أيوه تمام، خلاص عملتها", "نعم، اتحلت المشكلة والحمد لله", "اه خلصتها وكله تمام"]
NO_REPLIES = ["لا لسه معملتش", "للأسف ما قدرتش أعملها", "لأ، المشكلة لسه موجودة"]
UNCERTAIN_REPLIES = ["والله مش متأكد", "مش عارف بصراحة", "مش فاكر لو اتعملت"]
AGENT_REPLIES = ["عايز أكلم موظف", "ممكن أكلم حد من خدمة العملاء؟"]


def _phone() -> str:
    prefix = rng.choice(["+2010", "+2011", "+2012", "+2015"])
    return prefix + "".join(str(rng.randint(0, 9)) for _ in range(8))


def _customer_name() -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(SURNAMES)}"


def _transcript(ctx: GreetingContext, turns: list[tuple[str, str]]) -> str:
    lines = [f"المساعد: {greeting_text(ctx)}"]
    for customer, assistant in turns:
        lines.append(f"العميل: {customer}")
        lines.append(f"المساعد: {assistant}")
    return "\n".join(lines)


def _seed_users(db) -> dict[str, User]:
    users = {}
    for i, (username, email, full_name, role) in enumerate(SEED_USERS):
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            hashed_password=_hash_password("changeme123"),
            role=role,
            is_active=True,
            # Staggered across the morning shift start so the roster looks lived-in.
            last_login_at=WINDOW_START
            + timedelta(days=WINDOW_DAYS - 1, hours=8, minutes=13 * i),
        )
        db.add(user)
        users[username] = user
    db.flush()
    return users


def _seed_kb(db) -> list[KBDocument]:
    docs = []
    for entry in KB_DOCS:
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
    for i in range(N_CUSTOMERS):
        phone = _phone()
        while phone in phones:  # customer phones are unique
            phone = _phone()
        phones.add(phone)
        customer = Customer(
            full_name=_customer_name(),
            phone=phone,
            email=f"customer{i + 1:02d}@example.com" if rng.random() < 0.4 else None,
            governorate=rng.choice(GOVERNORATES),
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
    # 40 tickets. Outcome plan tuned near the dashboard mock KPIs: 28 resolved first try,
    # 4 resolved on a retry after no-answer, 4 transferred to a human,
    # 2 unresolved after offers of help, 2 still queued for tonight's batch.
    plans = (
        ["resolved_first"] * 28 + ["resolved_retry"] * 4 + ["transferred"] * 4
        + ["unresolved"] * 2 + ["queued"] * 2
    )
    rng.shuffle(plans)

    for i, plan in enumerate(plans):
        procedure, issue = PROCEDURES[i % len(PROCEDURES)]
        created = WINDOW_START + timedelta(
            days=i % WINDOW_DAYS, hours=rng.randint(9, 17), minutes=rng.randint(0, 59)
        )
        # Every customer gets one ticket; the surplus tickets are repeat callers.
        customer = customers[i] if i < len(customers) else rng.choice(customers)
        ticket = FollowUpTicket(
            crm_ticket_id=f"CRM-2026-{1000 + i}",
            customer_id=customer.id,
            customer_name=customer.full_name,
            customer_phone=customer.phone,
            procedure=procedure,
            issue_summary=issue,
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
                    ctx, [(rng.choice(YES_REPLIES), RESOLVED_GOODBYE_AR)]
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
                    ctx, [(rng.choice(YES_REPLIES), RESOLVED_GOODBYE_AR)]
                ),
            )
        elif plan == "transferred":
            duration = max(90, int(rng.gauss(175, 30)))
            _call(
                outcome="transferred",
                duration_seconds=duration,
                completed_at=started + timedelta(seconds=duration),
                transcript=_transcript(ctx, [(rng.choice(AGENT_REPLIES), TRANSFER_AR)]),
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
                        (rng.choice(UNCERTAIN_REPLIES), repeat_question_text(ctx)),
                        (rng.choice(NO_REPLIES), OFFER_HELP_AR),
                    ],
                ),
            )
    return tickets, calls


def _seed_chat(db, users: dict[str, User], docs: list[KBDocument]) -> None:
    def cite(doc: KBDocument, snippet: str) -> dict:
        return {"document_id": doc.id, "title": doc.title, "snippet": snippet}

    conversations = [
        (
            "sara.elmasry",
            [
                (
                    "إزاي العميل يقدم شكوى للجهاز القومي لتنظيم الاتصالات؟",
                    "يقدم العميل الشكوى أولًا للشركة نفسها، وإذا لم تُحل خلال 48 ساعة "
                    "يصعّدها للجهاز عبر الرقم 155 (من 8 صباحًا حتى 10 مساءً) أو تطبيق "
                    "My NTRA أو البريد complaints@tra.gov.eg، مع ذكر رقم الشكوى المسجل "
                    "لدى الشركة، وبشرط أن يكون الرقم مملوكًا له.",
                    [cite(docs[1], "تقديم الشكوى إلى الشركة أولًا ثم التصعيد بعد 48 ساعة عبر 155")],
                ),
                (
                    "إيه كود معرفة الـ PUK لعميل فودافون؟",
                    "يطلب العميل ‎*888*رقم الخط#‎ من أي رقم آخر لمعرفة كود الـ PUK "
                    "الخاص بشريحته.",
                    [cite(docs[0], "لمعرفة كود الـ PUK اطلب ‎*888*رقم الخط#‎ من أي رقم آخر")],
                ),
            ],
        ),
        (
            "karim.hussein",
            [
                (
                    "إيه الخطوات اللي أقول عليها للعميل قبل ما نسجّل شكوى نت منزلي؟",
                    "قبل تسجيل الشكوى: إعادة تشغيل الراوتر بفصل الكهرباء دقيقة كاملة، "
                    "والتأكد من عدم نفاد الباقة ومن عدم وجود أجهزة تستهلكها في الخلفية، "
                    "وتجربة زر WPS. لو استمر العطل تُسجَّل الشكوى على 111 أو 19777 "
                    "ويصل رقم متابعة.",
                    [cite(docs[2], "أعد تشغيل الراوتر بفصل الكهرباء عنه لمدة دقيقة كاملة")],
                ),
            ],
        ),
        (
            "mona.ibrahim",
            [
                (
                    "العميل عايز ينقل رقمه لشبكة تانية، إيه الشروط؟",
                    "النقل مجاني ويتم خلال 24 ساعة: يقدّم طلبًا في فرع الشركة الجديدة "
                    "ببطاقة الرقم القومي ويستلم شريحة غير مفعّلة، بشرط أن يكون مالك "
                    "الرقم وأن يكون قد مضى على تشغيل الخط 4 أشهر على الأقل وبدون "
                    "مديونيات.",
                    [cite(docs[3], "نقل الرقم مجانًا خلال 24 ساعة بشرط ملكية الرقم ومرور 4 أشهر")],
                ),
                (
                    "الروبوت بيعمل إيه لو العميل طلب يكلم موظف؟",
                    "طلب العميل التحدث مع موظف يُنفَّذ فورًا في أي مرحلة من المكالمة، "
                    "ويُحوَّل إلى ممثل خدمة عملاء بشري.",
                    [cite(docs[4], "طلب العميل التحدث مع موظف يُنفَّذ فورًا في أي مرحلة")],
                ),
            ],
        ),
    ]

    for day_offset, (username, qa_pairs) in enumerate(conversations):
        opened = WINDOW_START + timedelta(days=10 + day_offset, hours=11)
        session = ChatSession(user=users[username], created_at=opened, updated_at=opened)
        db.add(session)
        db.flush()
        at = opened
        for question, answer, sources in qa_pairs:
            db.add(
                ChatMessage(
                    session_id=session.id, role="user", content=question,
                    sources=[], created_at=at,
                )
            )
            at += timedelta(seconds=2)
            db.add(
                ChatMessage(
                    session_id=session.id, role="assistant", content=answer,
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
    events = [
        ("sara.elmasry", "auth.login", "user", None),
        ("sara.elmasry", "chat.query", "chat_session", "1"),
        ("sara.elmasry", "kb.read", "kb_document", str(docs[1].id)),
        ("karim.hussein", "auth.login", "user", None),
        ("karim.hussein", "chat.query", "chat_session", "2"),
        ("mona.ibrahim", "chat.query", "chat_session", "3"),
        ("mona.ibrahim", "kb.read", "kb_document", str(docs[3].id)),
        ("hala.elshazly", "auth.login", "user", None),
        ("hala.elshazly", "report.view", "fcr_report", "1"),
        ("tarek.fathy", "report.view", "fcr_report", "1"),
        ("admin", "kb.upload", "kb_document", str(docs[0].id)),
    ]
    for i, (username, action, resource_type, resource_id) in enumerate(events):
        db.add(
            AuditLog(
                user_id=users[username].id,
                action=action,
                resource_type=resource_type,
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
            f"seeded: {len(users)} users, {len(customers)} customers, {len(docs)} kb docs, "
            f"{len(_tickets)} tickets, {len(calls)} call logs, chat history, 1 FCR report, "
            "audit trail"
        )
        print("\nuser roster:")
        for user in users.values():
            print(f"  id={user.id:<3} {user.username:<20} {user.role:<16} {user.full_name}")
        print("\ncustomer sample (first 8):")
        for customer in customers[:8]:
            print(
                f"  id={customer.id:<3} {customer.phone:<15} "
                f"{customer.governorate:<12} {customer.full_name}"
            )

    print("embedding KB documents via the TEI container:")
    with SessionLocal() as db:
        _embed_kb([db.get(KBDocument, i) for i in doc_ids])
    return 0


if __name__ == "__main__":
    sys.exit(main())
