# app/core/settings.py

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Core & Auth ───────────────────────────────────────────────
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Chat Settings ─────────────────────────────────────────────
    MAX_MESSAGE_LENGTH: int = 1000
    ASR_TIMEOUT_SECONDS: float = 15.0

    # ── Legacy Vector Store (single namespace) ────────────────────
    CHROMA_COLLECTION: str = "therapy"
    CHROMA_DIR: str = "./chroma_data"

    # ── RAG Namespaces ────────────────────────────────────────────
    CHROMA_NAMESPACE_THEORY: str = "theory"
    CHROMA_NAMESPACE_PLAN: str = "personal_plan"
    CHROMA_NAMESPACE_SESSION: str = "session_data"
    CHROMA_NAMESPACE_FUTURE: str = "future_me"  # ← NEW

    # ── LLM Settings ──────────────────────────────────────────────
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    """
    EVERY consumer must call *this* to load current env vars (no caching).
    """
    return Settings()
