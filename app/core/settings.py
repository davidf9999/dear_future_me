# app/core/settings.py
"""
Central settings – now using **Pydantic-v2 native** syntax.

Key changes
───────────
* Replaces old `class Config` with `model_config = ConfigDict(...)`.
* Uses `Field(validation_alias=…)` instead of `env=` (future-proof for v3).
* Adds `model_config["env_file"]`, so we keep .env loading.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Pydantic-settings native config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown env vars
    )

    # ── Core & Auth ────────────────────────────────────────────
    DATABASE_URL: str = Field(validation_alias="DATABASE_URL")
    SECRET_KEY: str = Field(validation_alias="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ── Flags ─────────────────────────────────────────────────
    DEMO_MODE: bool = Field(False, validation_alias="DEMO_MODE")
    DEBUG_SQL: bool = Field(False, validation_alias="DEBUG_SQL")

    # ── Chat settings ─────────────────────────────────────────
    MAX_MESSAGE_LENGTH: int = 1000
    ASR_TIMEOUT_SECONDS: float = 15.0

    # ── RAG Namespaces / vector store ─────────────────────────
    CHROMA_DIR: str = "./chroma_data"
    CHROMA_NAMESPACE_THEORY: str = "theory"
    CHROMA_NAMESPACE_PLAN: str = "personal_plan"
    CHROMA_NAMESPACE_SESSION: str = "session_data"
    CHROMA_NAMESPACE_FUTURE: str = "future_me"

    # ── LLM settings ──────────────────────────────────────────
    OPENAI_API_KEY: str = Field(validation_alias="OPENAI_API_KEY")
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
