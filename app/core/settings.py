# app/core/settings.py
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Core & Auth ───────────────────────────────────────────────
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ── Demo / feature flags ─────────────────────────────────────
    DEMO_MODE: bool = Field(False, env="DEMO_MODE")
    DEBUG_SQL: bool = Field(False, env="DEBUG_SQL")  # new flag for echo

    # ── Chat settings ────────────────────────────────────────────
    MAX_MESSAGE_LENGTH: int = 1000
    ASR_TIMEOUT_SECONDS: float = 15.0

    # ── RAG & LLM settings (unchanged) ───────────────────────────
    CHROMA_COLLECTION: str = "therapy"
    CHROMA_DIR: str = "./chroma_data"
    CHROMA_NAMESPACE_THEORY: str = "theory"
    CHROMA_NAMESPACE_PLAN: str = "personal_plan"
    CHROMA_NAMESPACE_SESSION: str = "session_data"
    CHROMA_NAMESPACE_FUTURE: str = "future_me"

    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # ← now cached
    """
    Return the app Settings, reading .env the first time and
    then re-using the same instance.
    Tests can override by calling `get_settings.cache_clear()`
    after changing environment variables.
    """
    return Settings()
