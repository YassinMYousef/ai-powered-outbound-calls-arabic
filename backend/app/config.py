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

    # Speech / LLM providers
    openai_api_key: str = ""  # Whisper STT + RAG answer generation

    # STT (OpenAI Whisper). Egyptian + MSA both transcribe under language="ar";
    # stt_prompt_ar seeds the model with in-domain Egyptian spelling/terms to bias
    # decoding (Whisper's `prompt` is a soft hint, capped at ~224 tokens).
    stt_model: str = "whisper-1"  # or gpt-4o-transcribe / gpt-4o-mini-transcribe
    stt_prompt_ar: str = ""

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

    # Telephony (Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    # E.164. Twilio does not sell Egyptian (+20) numbers — use a Twilio number from a
    # supported country, or a number you own that is verified as an outgoing caller ID.
    twilio_from_number: str = ""
    public_base_url: str = "http://localhost:8000"  # must be reachable by Twilio for webhooks

    # Auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"


settings = Settings()
