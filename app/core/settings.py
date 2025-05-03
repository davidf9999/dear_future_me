# app/core/settings.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Chat settings
    MAX_MESSAGE_LENGTH: int = 1000
    ASR_TIMEOUT_SECONDS: float = 15.0

    # Vector store / RAG
    CHROMA_COLLECTION: str = "therapy"
    CHROMA_DIR: str = "./chroma_data"

    # LLM
    OPENAI_API_KEY: str
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.7
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()  # Now importable as app.core.settings.settings
if __name__ == "__main__":
    print("Loaded DATABASE_URL =", settings.DATABASE_URL)
    print("Loaded SECRET_KEY length =", len(settings.SECRET_KEY))