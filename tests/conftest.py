# tests/conftest.py

from pydantic_settings import BaseSettings
from pydantic import Field
import pytest
from sqlalchemy import text
from app.db.session import get_async_session
from app.auth.models import UserTable

class Settings(BaseSettings):
    OPENAI_API_KEY: str = Field("", env="OPENAI_API_KEY")
    CHROMA_COLLECTION: str = Field("default", env="CHROMA_COLLECTION")
    CHROMA_DIR: str = Field("chroma_db", env="CHROMA_DIR")
    CHROMA_NAMESPACE_THEORY: str = Field("theory", env="CHROMA_NAMESPACE_THEORY")
    CHROMA_NAMESPACE_PLAN: str = Field("personal_plan", env="CHROMA_NAMESPACE_PLAN")
    CHROMA_NAMESPACE_SESSION: str = Field("session_data", env="CHROMA_NAMESPACE_SESSION")
    CHROMA_NAMESPACE_REFLECTIONS: str = Field(
        "reflections", env="CHROMA_NAMESPACE_REFLECTIONS"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()


@pytest.fixture(autouse=True)
async def clear_users_table():
    async for session in get_async_session():
        try:
            await session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
            await session.commit()
        except Exception as e:
            print(f"Error clearing users table: {e}")
            await session.rollback()
        finally:
            break
