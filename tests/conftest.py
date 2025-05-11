# tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")  # Keep this for Alembic in CI if needed

from app.auth.models import UserTable
from app.core.settings import get_settings  # Import get_settings for cache clearing
from app.db.init_db import init_db
from app.db.session import get_async_session

# Import the factory function instead of the global app instance
from app.main import create_app


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_db() -> None:
    """Create all tables once at session start (synchronous wrapper)."""
    # If init_db relies on settings, ensure they are loaded correctly for this session scope
    # For now, assuming init_db uses its own Settings() instance or a global one that's okay for setup.
    asyncio.run(init_db())


@pytest.fixture(autouse=True)
async def clear_users_table() -> AsyncGenerator[None, None]:
    """Empty the users table between tests that might insert rows."""
    async for session in get_async_session():
        await session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
        await session.commit()
        break
    yield


@pytest.fixture
def client(request, monkeypatch) -> TestClient:
    """
    Provides a TestClient instance by calling the app factory.
    Tests can mark themselves with @pytest.mark.demo_mode(False)
    to run with DEMO_MODE=false. Defaults to DEMO_MODE=true for tests not marked.
    """
    marker = request.node.get_closest_marker("demo_mode")
    run_in_demo_mode = True  # Default for tests
    if marker and marker.args[0] is False:
        run_in_demo_mode = False

    if run_in_demo_mode:
        monkeypatch.setenv("DEMO_MODE", "true")
        print("INFO (test fixture): DEMO_MODE set to true for this test.")
    else:
        monkeypatch.setenv("DEMO_MODE", "false")
        print("INFO (test fixture): DEMO_MODE set to false for this test.")

    # Crucially, clear settings cache so it reloads with the new DEMO_MODE
    # when create_app() calls get_settings()
    get_settings.cache_clear()

    # Create a fresh app instance for this test
    test_app = create_app()
    return TestClient(test_app)
