# /home/dfront/code/dear_future_me/tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio  # For @pytest_asyncio.fixture
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.auth.models import Base, SafetyPlanTable, UserProfileTable, UserTable
from app.core.settings import get_settings
from app.db.migrate import upgrade_head
from app.db.session import AsyncSessionMaker, get_async_session

# Import the factory function instead of the global app instance
from app.main import create_app


@pytest.fixture(scope="session")
def event_loop(request):  # This fixture overrides pytest-asyncio's default
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(None)  # Clean up global state


@pytest_asyncio.fixture(scope="session")
async def test_engine(event_loop) -> AsyncGenerator[AsyncEngine, None]:  # Depends on the session-scoped event_loop
    """
    Creates a single SQLAlchemy AsyncEngine for the entire test session.
    pytest-asyncio will ensure this runs on the provided session-scoped event loop.
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG_SQL)
    print(f"INFO (test_engine): Created test engine for {settings.DATABASE_URL}")
    yield engine
    print("INFO (test_engine): Disposing test engine.")
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_db(test_engine: AsyncEngine, event_loop) -> None:  # Depends on the session-scoped event_loop
    """
    Initializes the test database schema once at the start of the test session.
    1. Drops all known SQLAlchemy tables using the test_engine.
    2. Applies all Alembic migrations to create the current schema.
    """
    print("INFO (_bootstrap_db): Dropping all tables using test_engine...")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("INFO (_bootstrap_db): Applying Alembic migrations (upgrade_head)...")
    try:
        upgrade_head()
        print("INFO (_bootstrap_db): Alembic migrations applied successfully.")
    except Exception as e:
        print(f"ERROR (_bootstrap_db): Alembic upgrade_head FAILED: {e}")

        # Debug check after potential failure
        async def check_table_existence(engine_conn, table_name):
            def sync_check(conn_sync, name_sync):
                inspector = inspect(conn_sync)
                return inspector.has_table(name_sync)

            return await engine_conn.run_sync(sync_check, table_name)

        async with test_engine.connect() as conn_check:
            profile_exists = await check_table_existence(conn_check, UserProfileTable.__tablename__)
            user_exists = await check_table_existence(conn_check, UserTable.__tablename__)
            safety_exists = await check_table_existence(conn_check, SafetyPlanTable.__tablename__)
        print(
            f"DEBUG (_bootstrap_db after Alembic error): Table '{UserProfileTable.__tablename__}' exists: {profile_exists}"
        )
        print(f"DEBUG (_bootstrap_db after Alembic error): Table '{UserTable.__tablename__}' exists: {user_exists}")
        print(
            f"DEBUG (_bootstrap_db after Alembic error): Table '{SafetyPlanTable.__tablename__}' exists: {safety_exists}"
        )

        # As a fallback if Alembic fails, try creating tables directly.
        print("INFO (_bootstrap_db): FALLBACK - Attempting direct Base.metadata.create_all due to Alembic error...")
        try:
            async with test_engine.begin() as conn_fallback:
                await conn_fallback.run_sync(Base.metadata.create_all)
            print("INFO (_bootstrap_db): FALLBACK - Direct Base.metadata.create_all completed.")
        except Exception as create_all_e:
            print(f"ERROR (_bootstrap_db): FALLBACK - Direct Base.metadata.create_all ALSO FAILED: {create_all_e}")
            raise create_all_e
    print("INFO (_bootstrap_db): Test database schema initialized.")


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a SQLAlchemy AsyncSession for each test function.
    """
    TestScopedSessionMaker = AsyncSessionMaker.__class__(bind=test_engine, expire_on_commit=False)
    async with TestScopedSessionMaker() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def clear_tables_before_test(db_session: AsyncSession) -> None:
    """
    Ensures relevant tables are empty before each test.
    """
    try:
        await db_session.execute(text(f"DELETE FROM {SafetyPlanTable.__tablename__}"))
        await db_session.execute(text(f"DELETE FROM {UserProfileTable.__tablename__}"))
        await db_session.execute(text(f"DELETE FROM {UserTable.__tablename__}"))
        await db_session.commit()
    except Exception as e:
        print(f"ERROR (clear_tables_before_test): Failed to clear tables: {e}")

        async def check_table_existence_in_session(s, table_name):
            try:
                await s.execute(text(f"SELECT 1 FROM {table_name} LIMIT 0"))
                return True
            except Exception:
                return False

        profile_exists = await check_table_existence_in_session(db_session, UserProfileTable.__tablename__)
        user_exists = await check_table_existence_in_session(db_session, UserTable.__tablename__)
        safety_exists = await check_table_existence_in_session(db_session, SafetyPlanTable.__tablename__)
        print(
            f"DEBUG (clear_tables_before_test after error): Table '{UserProfileTable.__tablename__}' exists: {profile_exists}"
        )
        print(f"DEBUG (clear_tables_before_test after error): Table '{UserTable.__tablename__}' exists: {user_exists}")
        print(
            f"DEBUG (clear_tables_before_test after error): Table '{SafetyPlanTable.__tablename__}' exists: {safety_exists}"
        )
        raise


@pytest.fixture(scope="function")
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine) -> TestClient:
    """
    Provides a TestClient instance for FastAPI.
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
