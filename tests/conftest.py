# tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.auth.models import Base, UserProfileTable, UserTable
from app.core.settings import get_settings
from app.db.migrate import upgrade_head
from app.db.session import AsyncSessionMaker, get_async_session

# Import the factory function instead of the global app instance
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop(request):  # Renamed from event_loop_instance to event_loop to override pytest-asyncio's default
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine(event_loop) -> AsyncGenerator[AsyncEngine, None]:  # Depends on session-scoped event_loop
    """
    Creates a single SQLAlchemy AsyncEngine for the entire test session.
    This engine is used for all database interactions in tests to ensure consistency.
    """
    settings = get_settings()  # Load settings once to get DATABASE_URL
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG_SQL)
    print(f"INFO (test_engine): Created test engine for {settings.DATABASE_URL}")
    yield engine
    print("INFO (test_engine): Disposing test engine.")
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_db(test_engine: AsyncEngine, event_loop) -> None:  # Depends on session-scoped event_loop
    """
    Initializes the test database schema once at the start of the test session.
    1. Drops all known SQLAlchemy tables using the test_engine.
    2. Applies all Alembic migrations to create the current schema.
    3. (Debug) Ensures tables are created via direct Base.metadata.create_all as a fallback.
    """
    print("INFO (_bootstrap_db): Dropping all tables using test_engine...")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("INFO (_bootstrap_db): Applying Alembic migrations (upgrade_head)...")
    try:
        upgrade_head()
        print("INFO (_bootstrap_db): Alembic migrations applied.")
        # Fallback/Verification: Ensure tables are created if migrations didn't (e.g., empty DB)
        print("INFO (_bootstrap_db): Attempting direct Base.metadata.create_all with test_engine...")
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("INFO (_bootstrap_db): Direct Base.metadata.create_all completed.")
    except Exception as e:
        print(f"ERROR (_bootstrap_db): Alembic upgrade_head or create_all failed: {e}")

        # Check if tables exist even if upgrade_head or create_all had issues
        async def table_exists_sync(engine_conn, table_name_sync):
            from sqlalchemy import inspect  # Local import

            inspector = inspect(engine_conn)
            return inspector.has_table(table_name_sync)

        async with test_engine.connect() as conn_check:
            profile_exists = await conn_check.run_sync(table_exists_sync, UserProfileTable.__tablename__)
            user_exists = await conn_check.run_sync(table_exists_sync, UserTable.__tablename__)
        print(f"DEBUG (_bootstrap_db after error): Table '{UserProfileTable.__tablename__}' exists: {profile_exists}")
        print(f"DEBUG (_bootstrap_db after error): Table '{UserTable.__tablename__}' exists: {user_exists}")
        raise
    print("INFO (_bootstrap_db): Test database schema initialized.")


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean SQLAlchemy AsyncSession for each test function,
    derived from the session-scoped test_engine.
    """
    TestScopedSessionMaker = AsyncSessionMaker.__class__(bind=test_engine, expire_on_commit=False)
    async with TestScopedSessionMaker() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)  # Runs for every test function
async def clear_tables_before_test(db_session: AsyncSession) -> None:
    """
    Ensures UserProfileTable and UserTable are empty before each test.
    Uses the function-scoped db_session.
    """
    try:
        await db_session.execute(text(f"DELETE FROM {UserProfileTable.__tablename__}"))
        await db_session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
        await db_session.commit()
    except Exception as e:
        print(f"ERROR (clear_tables_before_test): Failed to clear tables: {e}")

        async def table_exists(session_check, table_name_check):
            try:
                query = text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name_check}'")
                result = await session_check.execute(query)
                return result.scalar_one_or_none() is not None
            except Exception as query_exc:
                print(f"ERROR (clear_tables_before_test - table_exists check): {query_exc}")
                return False

        profile_exists = await table_exists(db_session, UserProfileTable.__tablename__)
        user_exists = await table_exists(db_session, UserTable.__tablename__)
        print(
            f"DEBUG (clear_tables_before_test after error): Table '{UserProfileTable.__tablename__}' exists: {profile_exists}"
        )
        print(f"DEBUG (clear_tables_before_test after error): Table '{UserTable.__tablename__}' exists: {user_exists}")
        raise


@pytest.fixture(scope="function")
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine) -> TestClient:
    """
    Provides a TestClient instance for FastAPI, configured for testing.
    - Handles DEMO_MODE based on test markers.
    - Overrides the application's database session dependency to use the test_engine.
    """
    marker = request.node.get_closest_marker("demo_mode")
    run_in_demo_mode = True
    if marker and marker.args and marker.args[0] is False:
        run_in_demo_mode = False

    monkeypatch.setenv("DEMO_MODE", "true" if run_in_demo_mode else "false")
    get_settings.cache_clear()

    test_app = create_app()

    AppTestSessionMaker = AsyncSessionMaker.__class__(bind=test_engine, expire_on_commit=False)

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with AppTestSessionMaker() as session:
            yield session

    test_app.dependency_overrides[get_async_session] = override_get_async_session
    return TestClient(test_app)
