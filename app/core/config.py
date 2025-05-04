# app/core/config.py

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field("", env="OPENAI_API_KEY")
    CHROMA_COLLECTION: str = Field("default", env="CHROMA_COLLECTION")
    CHROMA_DIR: str = Field("chroma_db", env="CHROMA_DIR")
    CHROMA_NAMESPACE_THEORY: str = Field("theory", env="CHROMA_NAMESPACE_THEORY")
    CHROMA_NAMESPACE_REFLECTIONS: str = Field(
        "reflections", env="CHROMA_NAMESPACE_REFLECTIONS"
    )

    class Config:
        extra = "ignore"  # ← swallow any other env vars (DATABASE_URL, SECRET_KEY,…)
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
