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
from typing import Literal

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    # ── Service Ports & Host ───────────────────────────────────
    # These will be overridden by .env.dev or .env.prod via run.sh
    DFM_API_HOST: str = Field("0.0.0.0", validation_alias="DFM_API_HOST")
    DFM_API_PORT: int = Field(8000, validation_alias="DFM_API_PORT")  # Default for prod
    STREAMLIT_SERVER_PORT: int = Field(8501, validation_alias="STREAMLIT_SERVER_PORT")  # Default for prod

    # ── Flags ─────────────────────────────────────────────────
    DEMO_MODE: bool = Field(False, validation_alias="DEMO_MODE")  # Server's DEMO_MODE, e.g., for DB reset
    DEBUG_SQL: bool = Field(False, validation_alias="DEBUG_SQL")

    # ── Chat settings ─────────────────────────────────────────
    MAX_MESSAGE_LENGTH: int = Field(1000)
    ASR_TIMEOUT_SECONDS: float = 15.0

    # ── RAG Namespaces / vector store ─────────────────────────
    CHROMA_DIR: str = Field(validation_alias="CHROMA_DB_PATH")
    CHROMA_NAMESPACE_THEORY: str = "theory"
    CHROMA_NAMESPACE_PLAN: str = "personal_plan"
    CHROMA_NAMESPACE_SESSION: str = "session_data"
    CHROMA_NAMESPACE_FUTURE: str = "future_me"

    # ── LLM settings ──────────────────────────────────────────
    OPENAI_API_KEY: str = Field(validation_alias="OPENAI_API_KEY")
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7

    # Demo user credentials (primarily for client tools like cli.py)
    DEMO_USER_EMAIL: str = Field(validation_alias="DEMO_USER_EMAIL")
    DEMO_USER_PASSWORD: str = Field(validation_alias="DEMO_USER_PASSWORD")

    # ── Language Settings ─────────────────────────────────────
    APP_DEFAULT_LANGUAGE: Literal["en", "he"] = Field("he", validation_alias="APP_DEFAULT_LANGUAGE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    ALWAYS call this helper instead of instantiating `Settings()` directly.
    Tests rely on the .cache_clear() method, and production code benefits
    from caching.
    """
    return Settings()  # type: ignore[call-arg]
