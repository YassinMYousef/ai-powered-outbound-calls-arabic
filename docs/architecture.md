# CallCenter — System Model & Flowcharts

Architecture diagrams for the Arabic AI call-center platform. Diagrams are grounded in the code
under `backend/app/` as of 2026-07-09 — the repo is an early skeleton, so most boxes describe
**design intent** (stubs raising `NotImplementedError` / HTTP 501), not working code.

**Status legend used below**

| Marker | Meaning |
|---|---|
| ✅ | Implemented: `/health`, `telephony/client.place_call`, `POST /telephony/voice`, `POST /telephony/status` |
| ⏳ / dashed | Stub — signature and contract exist, body raises `NotImplementedError` or returns 501 |

> GitHub and the VS Code Markdown preview (with Mermaid support) render these blocks as diagrams.
> Ready-to-share exports (SVG + high-res PNG) of every figure live in [`docs/diagrams/`](diagrams/).

---

## 1. System architecture

One node per module: how the six backend modules, the React dashboard, the data stores, and the
external providers fit together, and how the two products (outbound follow-up calls, agent RAG
chatbot) share them. Provider SDKs stay behind module wrappers so every vendor is swappable.
Detail for each flow lives in figures 2–5.

```mermaid
flowchart LR
    classDef mod fill:#f6f4ee,stroke:#8a8577
    classDef ext fill:#e3f2fd,stroke:#1565c0
    classDef store fill:#ede7f6,stroke:#4527a0
    classDef actor fill:#fce4ec,stroke:#ad1457
    classDef fe fill:#e8f5e9,stroke:#2e7d32

    QA(["📈 Quality team"]):::actor
    HAGENT(["🎧 Human agent"]):::actor
    CUST(["📞 Customer"]):::actor

    FE["<b>React dashboard</b><br/>DashboardPage · ChatWidget"]:::fe

    subgraph BE["FastAPI backend — backend/app"]
        API["<b>app/api</b><br/>calls · reports · chat · kb"]:::mod
        WK["<b>app/workers</b> — Celery<br/>batches · retries · ingest"]:::mod
        TEL["<b>app/telephony</b><br/>place_call ✅ webhooks ✅"]:::mod
        SP["<b>app/speech</b><br/>stt · tts · audio"]:::mod
        CONV["<b>app/conversation</b><br/>dialog · rag"]:::mod
        DATA["<b>app/data</b><br/>models · reporting · auth"]:::mod
    end

    subgraph STORES["Data stores"]
        PG[("Postgres 18 + pgvector")]:::store
        RD[("Redis 7")]:::store
    end

    subgraph PROV["External providers — swappable"]
        TW["Twilio Voice"]:::ext
        OAI["OpenAI — Whisper + LLM"]:::ext
        TTSP["Arabic TTS — TBD"]:::ext
        TEI["TEI — multilingual-e5 embeddings (local)"]:::ext
    end

    QA --> FE
    HAGENT --> FE
    FE -->|"/api/*"| API
    API -->|"chat · kb"| CONV
    API -->|"reports"| DATA
    API -->|"call batch"| WK
    WK -->|"place call"| TEL
    WK -->|"nightly ingest"| CONV
    WK -->|"FCR report"| DATA
    WK --- RD
    TEL -->|"dial + webhooks"| TW
    TW ---|"voice call"| CUST
    TEL -->|"turn audio"| SP
    SP -->|"transcript"| CONV
    CONV -->|"reply text"| SP
    TEL -->|"outcome"| DATA
    TEL -.->|"transfer"| HAGENT
    DATA --- PG
    SP -->|"Whisper STT"| OAI
    SP -->|"synthesize"| TTSP
    CONV -->|"LLM answer"| OAI
    CONV -->|"embed"| TEI
    CONV -->|"vectors (kb_chunks)"| PG
```

---

## 2. Outbound follow-up call loop (sequence)

The end-to-end loop that crosses every module: Celery enqueues → Twilio dials → webhooks drive
each dialog turn through speech + dialog → outcome lands in `CallLog` → reporting aggregates it.
Today `/voice` plays a static `<Say>` greeting and `/gather` is a stub; the dynamic-TTS steps are
the target design.

```mermaid
sequenceDiagram
    autonumber
    participant W as Celery worker<br/>(workers/tasks)
    participant T as Twilio Voice
    participant C as Customer
    participant H as FastAPI webhooks<br/>(/telephony/*)
    participant S as app/speech<br/>(audio · stt · tts)
    participant D as app/conversation<br/>(dialog)
    participant DB as Postgres<br/>(CallLog)

    Note over W: schedule_follow_up_batch — customers flagged from CRM / inbound records
    W->>W: enqueue place_outbound_call(call_id)
    W->>T: client.place_call(to, call_id)<br/>webhook URLs carry call_id
    T->>C: dials customer
    C-->>T: answers
    T->>H: POST /telephony/voice?call_id=…
    H->>S: tts.synthesize(Arabic greeting + ticket details)
    H-->>T: TwiML — play greeting, Gather speech
    T->>C: plays Arabic greeting
    C-->>T: speaks reply (نعم / لا / غير متأكد / طلب موظف)
    loop each dialog turn
        T->>H: POST /telephony/gather (audio)
        H->>S: audio.telephony_to_wav → stt.transcribe (Whisper)
        S-->>H: Arabic transcript
        H->>D: classify_intent → next_action
        alt MARK_RESOLVED (نعم)
            H->>DB: CallLog.outcome = resolved
            H-->>T: TwiML — closing message, hang up
        else OFFER_HELP / REPEAT_QUESTION (لا / غير متأكد)
            H->>S: tts.synthesize(follow-up reply)
            H-->>T: TwiML — play reply, Gather again
        else TRANSFER_TO_AGENT (agent request or repeated failure)
            H->>T: call_flow.transfer_to_agent(call_sid)
            H->>DB: CallLog.outcome = transferred
        end
    end
    T->>H: POST /telephony/status (completed / no-answer / failed)
    H->>DB: persist outcome + duration
    H->>W: call_flow.should_retry(outcome, attempts) → re-enqueue if attempts < 3
    Note over DB: data/reporting aggregates CallLog → FCR report → /api/reports → dashboard
```

---

## 3. Dialog decision tree

Design intent for `conversation/dialog.py` (`classify_intent` / `next_action` are stubs): the
four intents map to actions, with repeated لا / غير متأكد replies or STT failures escalating to a
human agent per `call_flow.transfer_to_agent`'s contract.

```mermaid
flowchart TD
    A(["Customer reply — Arabic audio from Gather"]) --> B["stt.transcribe (Whisper)"]
    B -->|transcript| C{"classify_intent"}
    B -->|"STT failed"| F
    C -->|"نعم — yes, step completed"| Y["MARK_RESOLVED"]
    C -->|"لا — no, not completed"| N["OFFER_HELP"]
    C -->|"غير متأكد — uncertain"| U["REPEAT_QUESTION / clarify"]
    C -->|"طلب موظف — asks for a live agent"| G["TRANSFER_TO_AGENT"]
    Y --> Y2(["END_CALL — CallLog.outcome = resolved"])
    N --> H2{"help resolves it this turn?"}
    H2 -->|yes| Y
    H2 -->|"no — repeated لا"| G
    U --> F{"turn < retry limit?"}
    F -->|yes| R(["re-Gather — next dialog turn"])
    F -->|"no — repeated uncertainty / STT failures"| G
    G --> G2(["Bridge to human agent — outcome = transferred"])
```

---

## 4. Call outcome & retry policy

What happens after Twilio posts the final status to `/telephony/status`. Retry policy lives in
`telephony/call_flow.py` (`MAX_ATTEMPTS = 3`); every terminal outcome feeds `data/reporting.py`
and its KPI targets (FCR ≥ 90%, completion rate vs. live-agent baseline).

```mermaid
flowchart TD
    S["Twilio POST /telephony/status — CallStatus + duration"] --> P["persist to CallLog (outcome, duration_seconds, attempts)"]
    P --> O{"call outcome"}
    O -->|"completed — resolved"| R(["Resolved — counts toward FCR ≥ 90% target"])
    O -->|"completed — unresolved"| UNR(["Unresolved — quality team follow-up"])
    O -->|"transferred"| TRF(["Handled by human agent — lowers completion-rate KPI"])
    O -->|"no-answer / failed"| RT{"should_retry? attempts < MAX_ATTEMPTS = 3"}
    RT -->|yes| RQ["re-enqueue place_outbound_call (attempts + 1)"]
    RQ --> DIAL["Twilio dials again → back to call loop"]
    RT -->|no| GU(["Final: no_answer — max attempts exhausted"])
    R --> REP["data/reporting → FCR report → /api/reports → dashboard"]
    UNR --> REP
    TRF --> REP
    GU --> REP
```

---

## 5. RAG knowledge-base loops

The agent-facing chatbot's two paths. Ingestion runs nightly (Celery) and on upload via
`/api/kb`; queries flow through the role guard (KB content is proprietary) to retrieval and
cited answer generation — citations are a hard requirement.

```mermaid
flowchart LR
    subgraph ING["Ingestion path — nightly Celery task + on-demand upload"]
        direction TB
        UP["POST /api/kb — document upload"] --> DOC["KBDocument row — extracted text"]
        CRON["Celery: ingest_kb_documents (nightly)"] --> PICK["pick new / changed docs"]
        DOC --> PIPE
        PICK --> PIPE["ingest.ingest_document — extract → chunk → embed"]
        PIPE --> UPSERT["upsert vectors + source metadata"]
        UPSERT --> STAMP["stamp KBDocument.embedded_at (coverage KPI)"]
    end

    subgraph QRY["Query path — agent chatbot"]
        direction TB
        Q(["Agent asks in ChatWidget — Arabic, RTL"]) --> CAPI["POST /api/chat/query"]
        CAPI --> GUARD{"auth.require_role — KB is proprietary"}
        GUARD -->|authorized| RET["retrieve.retrieve(query_ar, top_k=5)"]
        GUARD -->|denied| DENY(["403"])
        RET --> ANS["answer.answer — LLM composes Arabic answer"]
        ANS --> OUT(["Answer + cited sources (المصدر: …) → ChatWidget"])
    end

    PG[("Postgres + pgvector — KBDocument, kb_chunks")]
    TEI["TEI — multilingual-e5-large embeddings (local)"]
    ANT["Anthropic — cited answer LLM (Sonnet 5)"]

    UP --> PG
    UPSERT --> PG
    STAMP --> PG
    RET --> PG
    PIPE --> TEI
    ANS --> ANT
```
