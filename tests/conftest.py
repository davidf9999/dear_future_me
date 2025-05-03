# tests/conftest.py
import os
import pytest
import asyncio
from app.db.init_db import init_db


@pytest.fixture(autouse=True, scope="session")
def set_test_env():
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")


@pytest.fixture(autouse=True, scope="session")
def initialize_db():
    """Initialize the database before running tests."""
    asyncio.run(init_db())


@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    # Provide a dummy key so OpenAIEmbeddings init doesn’t error
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")