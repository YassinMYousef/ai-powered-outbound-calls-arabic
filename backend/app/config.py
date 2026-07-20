"""Central settings — modules read config from here, never os.environ directly.

New keys: add a field here, document it in .env.example, and (if it's infra)
add the service to docker-compose.yml.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Data stores
    database_url: str = "postgresql+psycopg://callcenter:callcenter@localhost:5432/callcenter"
    redis_url: str = "redis://localhost:6379/0"

    # Central logging (Promtail tails this JSONL file and forwards it to Loki).
    log_level: str = "INFO"
    log_file: str = "logs/callcenter.jsonl"
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5

    # Speech / LLM providers
    openai_api_key: str = ""  # Whisper STT + RAG answer generation

    # STT (OpenAI Whisper). Egyptian + MSA both transcribe under language="ar";
    # stt_prompt_ar seeds the model with in-domain Egyptian spelling/terms to bias
    # decoding (Whisper's `prompt` is a soft hint, capped at ~224 tokens).
    stt_model: str = "whisper-1"  # or gpt-4o-transcribe / gpt-4o-mini-transcribe
    # Default seeds decoding with the exact yes/no/uncertain/agent vocabulary
    # dialog.classify_intent matches on, in both Egyptian and MSA spellings.
    stt_prompt_ar: str = (
        "مكالمة متابعة من خدمة العملاء. "
        "أيوه تمام، نعم تم حل المشكلة، اتحلت المشكلة، خلاص عملتها، "
        "لا لسه معملتش، لأ المشكلة لسه موجودة، "
        "مش متأكد، غير متأكد، مش عارف، "
        "عايز أكلم موظف، أريد التحدث مع ممثل خدمة العملاء."
    )
    # Hallucination gate (whisper-1 only — needs verbose_json segments). Whisper
    # invents fluent Arabic over silence/noise; a segment is kept only if
    # no_speech_prob <= max AND avg_logprob >= min. Thresholds are the ones the
    # reference OpenAI implementation uses for its silence heuristic.
    stt_no_speech_prob_max: float = 0.6
    stt_avg_logprob_min: float = -1.0

    # TTS (ElevenLabs). SDK-free — calls go through httpx in speech/tts.py so the
    # provider stays swappable behind synthesize().
    tts_provider: str = "elevenlabs"
    tts_api_key: str = ""  # ElevenLabs xi-api-key
    elevenlabs_base_url: str = "https://api.elevenlabs.io"
    elevenlabs_voice_id: str = "L10lEremDiJfPicq5CPh"
    # eleven_multilingual_v2 supports Arabic AND text normalization + pronunciation
    # dictionaries (the low-latency turbo/flash models only allow normalization="auto").
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    # ElevenLabs output_format. Default is natural-quality mp3; set to "ulaw_8000"
    # to get Twilio-ready audio straight from the API and skip speech/audio.py.
    elevenlabs_output_format: str = "mp3_44100_128"
    # Text normalization — spells out numbers/dates/currency so ticket IDs and
    # amounts in the greeting are read naturally. auto | on | off.
    elevenlabs_text_normalization: str = "auto"
    # Custom pronunciation dictionary (proper nouns, product/plan names). Both IDs
    # required to activate; leave blank to send no locator.
    elevenlabs_pronunciation_dictionary_id: str = ""
    elevenlabs_pronunciation_dictionary_version_id: str = ""
    # voice_settings tuning
    elevenlabs_stability: float = 0.5
    elevenlabs_similarity_boost: float = 0.75
    elevenlabs_style: float = 0.0
    elevenlabs_use_speaker_boost: bool = True

    # RAG — embeddings via a local TEI container (docker-compose `tei` service),
    # vectors in Postgres via pgvector (kb_chunks). No external vector-DB SaaS.
    tei_url: str = "http://localhost:8080"
    embedding_model: str = "intfloat/multilingual-e5-large"  # informational — TEI picks the model
    embedding_dimensions: int = 1024  # must match the model AND kb_chunks.embedding
    rag_chunk_size: int = 1500  # characters ≈ 400–500 Arabic tokens
    rag_chunk_overlap: int = 200
    rag_top_k: int = 5  # passages retrieved per question

    # RAG answer generation (Anthropic). Citations are a hard requirement, so the
    # answer is grounded with the Citations API — see conversation/rag/answer.py.
    anthropic_api_key: str = ""
    answer_model: str = "claude-sonnet-5"  # grounded extraction; Opus is overkill here
    answer_max_tokens: int = 1024  # a concise agent-facing answer, not an essay
    # low | medium | high | xhigh | max. Measured: "low" stitches near-verbatim quotes
    # and restates the same step twice — and spent MORE output tokens doing it
    # (207 vs 146). "medium" composes cleanly; it is both better and cheaper here.
    answer_effort: str = "medium"

    # RAG query cache — two levels checked before answering: L0 exact-match
    # (Redis, Arabic-normalized key) and L1 semantic (pgvector, cosine over cached
    # query embeddings). A hit returns the cached {answer, sources} and skips both
    # retrieval and generation. Keys include answer_model, so a model change never
    # serves stale answers; KB ingestion flushes both levels before the TTL does.
    rag_query_cache_enabled: bool = True
    rag_query_cache_ttl_seconds: int = 86400
    # Cosine floor for an L1 hit. e5-large similarities compress into ~0.7–1.0:
    # same-intent Arabic paraphrases score >=0.95 while related-but-different
    # questions land ~0.90–0.94. 0.95 favors precision — a wrong cached procedure
    # to an agent on a live call is worse than a cache miss.
    rag_query_cache_similarity_threshold: float = 0.95

    # Unanswered-question (KB gap) log. Every chat turn the KB cannot answer is
    # recorded to unanswered_questions for admins to review and fill — see
    # data/kb_gaps.py. A gap is one of three coverage verdicts from rag/answer.py:
    #   no_match       — retrieval returned nothing at all,
    #   no_citation    — passages were retrieved but the grounded model cited none,
    #   low_confidence — an answer was cited, but the best passage's raw cosine
    #                    similarity fell below rag_gap_min_similarity.
    # RRF-fused retrieval scores can't gate confidence (a strong semantic-only
    # paraphrase match scores like a weak one), so the low_confidence gate uses the
    # dense arm's raw cosine — the same signal the query cache trusts. e5 cosine
    # compresses into ~0.7-1.0; below ~0.80 the best passage is off-topic enough
    # that a cited answer is more likely a near-miss than real coverage. Conservative
    # on purpose: a false gap is admin noise, and no_match/no_citation already catch
    # the clear cases.
    kb_gap_logging_enabled: bool = True
    rag_gap_min_similarity: float = 0.80

    # Chat conversation memory. Every turn is persisted per chat_sessions row; only
    # a bounded window is replayed to the model. Follow-up questions are condensed
    # into one standalone Arabic query (Haiku-class, cheap) BEFORE hybrid retrieval;
    # the first turn of a session skips the rewrite entirely.
    chat_history_max_messages: int = 10  # messages (5 exchanges) sent to the answer prompt
    rewrite_model: str = "claude-haiku-4-5"
    rewrite_max_tokens: int = 150  # one rewritten Arabic question, not an essay
    rewrite_history_max_messages: int = 6  # messages the rewriter sees

    # Telephony (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # E.164. Twilio does not sell Egyptian (+20) numbers — use a Twilio number from a
    # supported country, or a number you own that is verified as an outgoing caller ID.
    twilio_from_number: str = ""
    public_base_url: str = "http://localhost:8000"  # must be reachable by Twilio for webhooks
    # E.164 human-agent transfer target. Empty means apologize and end the call.
    human_agent_number: str = ""
    # <Record> endpointing: keep recording until the caller goes silent for
    # record_silence_timeout_seconds; record_max_length_seconds is only the
    # safety cap for a turn (Twilio hard-stops the recording when it is hit).
    record_max_length_seconds: int = 30
    record_silence_timeout_seconds: int = 2
    # Per-call speech token lifetime and reusable synthesized-audio cache lifetime.
    telephony_audio_ttl_seconds: int = 600
    tts_cache_ttl_seconds: int = 86400

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"


settings = Settings()
