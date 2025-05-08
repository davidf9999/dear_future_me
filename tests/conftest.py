# tests/conftest.py
"""
Global test fixtures.

Changes
───────
* Uses a SAVEPOINT strategy to reset DB state after each test instead of
  explicit DELETEs → no “coroutine was never awaited” warnings.
"""

from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text

from app.core.settings import get_settings
from app.db.session import AsyncSessionMaker
from app.auth.models import Base  # metadata for creating tables


# ── Reset cached settings so env-var changes per test are honoured ───────
@pytest.fixture(autouse=True, scope="function")
def _reset_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Provide an isolated transaction for each test ───────────────────────
@asynccontextmanager
async def _test_session():
    """
    Open a session inside a SAVEPOINT so we can roll everything back when
    the test finishes (much faster & cleaner than DELETE).
    """
    async with AsyncSessionMaker() as session:
        await session.execute(text("SAVEPOINT test_sp"))
        try:
            yield session
        finally:
            await session.execute(text("ROLLBACK TO SAVEPOINT test_sp"))
            await session.commit()  # release locks


@pytest.fixture
async def db_session():
    async with _test_session() as s:
        yield s


# ── Clear all tables once at session start if DEMO_MODE enabled ─────────
@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    """
    In DEMO_MODE the DB is recreated at startup, but tests that run with a
    different DATABASE_URL (e.g. tmp file) need tables. Create once.
    """
    cfg = get_settings()
    if cfg.DATABASE_URL.startswith("sqlite"):
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(cfg.DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
