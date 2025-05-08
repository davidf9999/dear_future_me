# tests/conftest.py
# ruff: noqa: E402
# tests/conftest.py
"""
Global test fixtures.

* Creates the SQLite schema exactly once per test session.
* Forces DEMO_MODE=true so chat endpoints stay public on CI.
* Provides a function-scope fixture to clear the users table between tests.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from sqlalchemy import text

# --------------------------------------------------------------------------- #
# 1)  Make sure the app reads a predictable environment
# --------------------------------------------------------------------------- #
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
# If you use DEBUG_SQL etc. add them here as well.

from app.auth.models import UserTable

# 2)  Import *after* env-vars so Settings picks them up
from app.db.init_db import init_db
from app.db.session import get_async_session


# --------------------------------------------------------------------------- #
# 3)  Bootstrap the schema once for the whole test run
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def _bootstrap_db() -> None:
    """Create all tables once at session start (synchronous wrapper)."""
    asyncio.run(init_db())  # init_db already drops & creates all tables


# --------------------------------------------------------------------------- #
# 4)  Function-scope fixture to clear users table (keeps tests isolated)
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
async def clear_users_table() -> AsyncGenerator[None, None]:
    """Empty the users table between tests that might insert rows."""
    async for session in get_async_session():  # async generator dependency
        await session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
        await session.commit()
        break
    yield
