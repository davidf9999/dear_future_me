# tests/conftest.py
"""
Shared pytest fixtures for the Dear Future Me test-suite.

Key points
──────────
* `app.core.settings.get_settings()` is now cached with @lru_cache, so we
  clear that cache once per test (autouse fixture) to honour any
  `monkeypatch.setenv()` calls a test might do.

* We no longer define a shadow Settings class here; the real one is used.

* The `clear_users_table` fixture keeps the auth table empty across tests
  by checking out a single `AsyncSession` from the global pool.
"""

import pytest
from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import get_async_session
from app.auth.models import UserTable


# ────────────────────────────────────────────────────────────────
# Ensure each test gets fresh Settings after env-var tweaks
# ────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def reset_settings_cache():
    """
    Clear the cached Settings object before *and* after every test
    so that environment-variable changes inside a test are respected.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ────────────────────────────────────────────────────────────────
# Keep the users table empty between tests
# ────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
async def clear_users_table():
    """
    Truncate the users table so tests don’t bleed data into one another.
    """
    async for session in get_async_session():
        try:
            await session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
            await session.commit()
        finally:
            break
