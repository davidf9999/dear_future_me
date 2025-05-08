# tests/conftest.py

import pytest
from sqlalchemy import text

from app.auth.models import UserTable
from app.db.init_db import init_db
from app.db.session import get_async_session


# ── 1. Ensure schema exists for the whole run ──────────────────────────
@pytest.fixture(scope="session", autouse=True)
async def _bootstrap_db():
    """
    CI uses a newer FastAPI/SQLAlchemy combo where @app.on_event('startup')
    is **not awaited** inside TestClient.  We call init_db() explicitly here
    so the `user` table is present before any test executes.
    """
    await init_db()
    yield


# ── 2. Per-test cleanup (same as before) ───────────────────────────────
@pytest.fixture(autouse=True)
async def clear_users_table():
    async for session in get_async_session():  # type: ignore[misc]
        try:
            await session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
            await session.commit()
        except Exception:
            await session.rollback()
        finally:
            break
