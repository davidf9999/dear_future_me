# tests/conftest.py
import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def set_test_env():
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
