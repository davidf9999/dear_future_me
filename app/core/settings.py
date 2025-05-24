# app/core/settings.py
# Full file content
import os
from enum import Enum
from typing import List, Optional

from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Dear Future Me"
    PROJECT_VERSION: str = "0.1.0"
    DESCRIPTION: str = "AI-powered mental wellness companion"
    API_PREFIX: str = "/api/v1"

    # General App Settings
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
    LOG_LEVEL: LogLevel = LogLevel.INFO
    RUN_ALEMBIC_ON_STARTUP: bool = os.getenv("RUN_ALEMBIC_ON_STARTUP", "true").lower() == "true"

    # Database settings
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "data/dev/database.db")
    DEBUG_SQL: bool = os.getenv("DEBUG_SQL", "false").lower() == "true"
    
    # Allow DATABASE_URL to be set directly for backward compatibility
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")
    
    @property
    def database_url(self) -> str:
        """Construct the database URL from SQLITE_DB_PATH if not explicitly set."""
        if self.DATABASE_URL:
            return self.DATABASE_URL
            
        # Ensure the path is absolute and normalized
        db_path = os.path.abspath(os.path.join(os.getcwd(), self.SQLITE_DB_PATH))
        # Ensure the directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # Return SQLAlchemy URL for SQLite
        return f"sqlite+aiosqlite:///{db_path}"
    
    # Alias for backward compatibility
    @property
    def DATABASE_URL(self) -> str:
        """Alias for database_url for backward compatibility."""
        return self.database_url
    
    # For asyncpg: "postgresql+asyncpg://user:password@host:port/dbname"

    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # OpenAI settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "your_openai_api_key_here")
    LLM_MODEL: str = "gpt-3.5-turbo"
    LLM_TEMPERATURE: float = 0.7
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    MAX_MESSAGE_LENGTH: int = 1000  # Restored based on error
    ASR_TIMEOUT_SECONDS: int = 60  # Restored from old version

    # ChromaDB settings
    CHROMA_HOST: Optional[str] = os.getenv("CHROMA_HOST", None)
    CHROMA_PORT: Optional[int] = int(os.getenv("CHROMA_PORT")) if os.getenv("CHROMA_PORT") else None
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

    # RAG Namespaces (Collections in ChromaDB)
    CHROMA_NAMESPACE_THEORY: str = "dfm_theory"
    CHROMA_NAMESPACE_PERSONAL_PLAN: str = "dfm_personal_plan"
    CHROMA_NAMESPACE_SESSION_DATA: str = "dfm_session_data"
    CHROMA_NAMESPACE_FUTURE_ME: str = "dfm_future_me"
    CHROMA_NAMESPACE_THERAPIST_NOTES: str = "dfm_therapist_notes"
    CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES: str = "dfm_chat_history_summaries"

    # Prompt template settings
    PROMPT_TEMPLATE_DIR: str = "templates"
    SYSTEM_PROMPT_FILE: str = "system_prompt.md"
    CRISIS_PROMPT_FILE: str = "crisis_prompt.md"

    # Crisis Keywords
    CRISIS_KEYWORDS: List[str] = [
        "die",
        "kill myself",
        "suicide",
        "hopeless",
        "end it all",
        "ending my life",
        "can't go on",
        "no reason to live",
    ]

    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]  # Example origins

    # Test settings (can be overridden by environment variables for testing)
    TEST_DATABASE_URL: str = os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test_override.db")
    # Test RAG Namespaces
    TEST_CHROMA_NAMESPACE_THEORY: str = "theory_test"
    TEST_CHROMA_NAMESPACE_PERSONAL_PLAN: str = "personal_plan_test"
    TEST_CHROMA_NAMESPACE_SESSION_DATA: str = "session_data_test"
    TEST_CHROMA_NAMESPACE_FUTURE_ME: str = "future_me_test"
    TEST_CHROMA_NAMESPACE_THERAPIST_NOTES: str = "therapist_notes_test"
    TEST_CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES: str = "dfm_chat_history_summaries_test"

    # Demo and other specific settings
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    DEMO_USER_EMAIL: Optional[str] = os.getenv("DEMO_USER_EMAIL", None)
    DEMO_USER_PASSWORD: Optional[str] = os.getenv("DEMO_USER_PASSWORD", None)
    APP_DEFAULT_LANGUAGE: str = os.getenv("APP_DEFAULT_LANGUAGE", "en")
    SKIP_AUTH: bool = os.getenv("SKIP_AUTH", "false").lower() == "true"
    STREAMLIT_DEBUG: bool = os.getenv("STREAMLIT_DEBUG", "false").lower() == "true"

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


_settings_instance = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance
