# /home/dfront/code/dear_future_me/app/core/settings.py
import os
from enum import Enum
from typing import Optional

import chromadb.config
from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    CRITICAL = "CRITICAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    DEBUG = "DEBUG"


class Settings(BaseSettings):
    # --- Core Application Settings ---
    APP_NAME: str = "Dear Future Me"
    APP_VERSION: str = "0.1.0"
    DEBUG_MODE: bool = False
    LOG_LEVEL: LogLevel = LogLevel.INFO
    # APP_DEFAULT_LANGUAGE: str = "en" # Removed language setting

    # --- Database Settings ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./test.db"
    DEBUG_SQL: bool = False

    # --- Authentication & Security ---
    SECRET_KEY: str = "a_very_secret_key_that_should_be_changed"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    DEMO_MODE: bool = True
    DEMO_USER_EMAIL: EmailStr = "demo@example.com"
    DEMO_USER_PASSWORD: str = "demopassword"
    RUN_ALEMBIC_ON_STARTUP: bool = True

    # --- LLM & RAG Settings ---
    OPENAI_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-3.5-turbo"
    LLM_TEMPERATURE: float = 0.7
    MAX_MESSAGE_LENGTH: int = 1000
    ASR_TIMEOUT_SECONDS: int = 60

    # --- ChromaDB RAG Namespaces ---
    CHROMA_NAMESPACE_THEORY: str = "theory"
    CHROMA_NAMESPACE_PERSONAL_PLAN: str = "personal_plan"
    CHROMA_NAMESPACE_SESSION_DATA: str = "session_data"
    CHROMA_NAMESPACE_FUTURE_ME: str = "future_me"
    CHROMA_NAMESPACE_THERAPIST_NOTES: str = "therapist_notes"
    CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES: str = "dfm_chat_history_summaries"

    CHROMA_DIR: str = "./chroma_data"
    CHROMA_HOST: Optional[str] = None
    CHROMA_PORT: Optional[int] = None

    # --- File Paths ---
    PROMPT_TEMPLATE_DIR: str = "templates"
    CRISIS_PROMPT_FILE: str = "crisis_prompt.md"
    SYSTEM_PROMPT_FILE: str = "system_prompt.md"

    # --- API Ports ---
    DFM_API_PORT: int = 8000
    STREAMLIT_SERVER_PORT: int = 8501

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def CHROMA_CLIENT_SETTINGS(self) -> chromadb.config.Settings:
        chroma_dir_to_use = self.CHROMA_DIR

        if self.CHROMA_HOST and self.CHROMA_PORT:
            return chromadb.config.Settings(
                chroma_api_impl="chromadb.api.fastapi.FastAPI",
                chroma_server_host=self.CHROMA_HOST,
                chroma_server_http_port=str(self.CHROMA_PORT),
            )
        else:
            return chromadb.config.Settings(is_persistent=True, persist_directory=chroma_dir_to_use)


_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings_instance
    if _settings_instance is None:
        env_file_path = os.getenv("ENV_FILE", ".env")
        if not os.path.exists(env_file_path) and env_file_path == ".env":
            if os.path.exists(".env.example"):
                env_file_path = ".env.example"
                print(f"INFO: Default .env file not found. Using {env_file_path} as a fallback.")
            else:
                print("WARNING: Neither .env nor .env.example found. Using default settings values.")

        current_model_config = Settings.model_config.copy()
        current_model_config["env_file"] = env_file_path

        _settings_instance = Settings(_model_config=current_model_config)
    return _settings_instance
