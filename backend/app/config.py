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
    tts_provider: str = ""    # Arabic neural voice provider — selection pending (Speech module)
    tts_api_key: str = ""

    # RAG / vector DB
    pinecone_api_key: str = ""
    pinecone_index: str = "callcenter-kb"

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
