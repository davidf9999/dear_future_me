# /home/dfront/code/dear_future_me/tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

from typing import AsyncGenerator

import pytest
import pytest_asyncio  # For @pytest_asyncio.fixture
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.auth.models import Base, SafetyPlanTable, UserProfileTable, UserTable
from app.core.settings import Settings, get_settings  # Ensure Settings is imported
from app.db.migrate import upgrade_head  # This will now be an async function
from app.db.session import AsyncSessionMaker, get_async_session

# Import the factory function instead of the global app instance
from app.main import create_app

# pytest-asyncio's event_loop fixture will now be session-scoped due to pytest.ini setting.


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """
    Creates a single SQLAlchemy AsyncEngine for the entire test session.
    It will run on the session-scoped event_loop provided by pytest-asyncio.
    """
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG_SQL)
    print(f"INFO (test_engine): Created test engine for {settings.DATABASE_URL}")
    yield engine
    print("INFO (test_engine): Disposing test engine.")
    await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_db(test_engine: AsyncEngine) -> None:
    """
    Initializes the test database schema once at the start of the test session.
    1. Drops all known SQLAlchemy tables.
    2. Applies all Alembic migrations to create the schema from scratch.
       If Alembic fails, this fixture will raise an error, as the schema is critical.
    """
    print("INFO (_bootstrap_db): Dropping all tables using test_engine...")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    print("INFO (_bootstrap_db): All tables dropped.")

    print("INFO (_bootstrap_db): Attempting to create schema via Alembic migrations (upgrade_head)...")
    try:
        await upgrade_head()  # Now awaiting the async version
        print("INFO (_bootstrap_db): Alembic migrations applied successfully.")
    except Exception as e_alembic:
        print(f"CRITICAL ERROR (_bootstrap_db): Alembic upgrade_head FAILED: {e_alembic}")

        # Attempt to check table status for debugging even on critical failure
        async def check_table_existence(engine_conn, table_name_to_check):
            def sync_check(conn_sync, name_sync):
                inspector = inspect(conn_sync)
                return inspector.has_table(name_sync)

            return await engine_conn.run_sync(sync_check, table_name_to_check)

        print("DEBUG (_bootstrap_db after Alembic CRITICAL error): Checking table existence...")
        async with test_engine.connect() as conn_check:
            user_table_exists = await check_table_existence(conn_check, UserTable.__tablename__)
            user_profile_exists = await check_table_existence(conn_check, UserProfileTable.__tablename__)
            safety_plan_exists = await check_table_existence(conn_check, SafetyPlanTable.__tablename__)
            print(
                f"DEBUG (_bootstrap_db after Alembic CRITICAL error): Table '{UserTable.__tablename__}' exists: {user_table_exists}"
            )
            print(
                f"DEBUG (_bootstrap_db after Alembic CRITICAL error): Table '{UserProfileTable.__tablename__}' exists: {user_profile_exists}"
            )
            print(
                f"DEBUG (_bootstrap_db after Alembic CRITICAL error): Table '{SafetyPlanTable.__tablename__}' exists: {safety_plan_exists}"
            )
        raise RuntimeError(f"Alembic migrations failed during test setup: {e_alembic}") from e_alembic

    print("INFO (_bootstrap_db): Final check of table existence after successful Alembic run...")
    async with test_engine.connect() as conn_final_check:
        all_tables_in_metadata = Base.metadata.tables.keys()
        all_exist_and_accounted_for = True
        for table_name_key in all_tables_in_metadata:
            table_obj = Base.metadata.tables[table_name_key]

            def sync_check_final(conn_sync_final, name_sync_final):
                inspector = inspect(conn_sync_final)
                return inspector.has_table(name_sync_final)

            exists = await conn_final_check.run_sync(sync_check_final, table_obj.name)
            print(f"INFO (_bootstrap_db final check): Table '{table_obj.name}' exists: {exists}")
            if not exists:
                all_exist_and_accounted_for = False

        if not all_exist_and_accounted_for:
            print(
                "CRITICAL ERROR (_bootstrap_db): Not all expected tables exist after Alembic migrations reported success. This indicates a severe discrepancy between models and migrations, or an issue with Alembic's execution/visibility."
            )
            raise RuntimeError("Schema verification failed after Alembic upgrade: Not all tables created.")
        else:
            print("INFO (_bootstrap_db): All expected tables confirmed to exist after Alembic migrations.")
    print("INFO (_bootstrap_db): Test database schema initialization process completed.")


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
    tables_to_clear = [SafetyPlanTable, UserProfileTable, UserTable]  # Order for FKs
    for table in tables_to_clear:
        try:
            await db_session.execute(text(f"DELETE FROM {table.__tablename__}"))
        except Exception as e:
            print(
                f"WARNING (clear_tables_before_test): Could not clear table {table.__tablename__}: {e}. It might not exist."
            )
    try:
        await db_session.commit()
    except Exception as e_commit:
        print(f"ERROR (clear_tables_before_test): Commit failed after attempting to clear tables: {e_commit}")
        await db_session.rollback()


@pytest.fixture(scope="function")
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine) -> TestClient:
    """
    Provides a TestClient instance for FastAPI.
    """
    marker = request.node.get_closest_marker("demo_mode")
    run_in_demo_mode = True
    if marker and marker.args and marker.args[0] is False:
        run_in_demo_mode = False

    original_env_file = Settings.model_config.get("env_file")
    Settings.model_config["env_file"] = None
    get_settings.cache_clear()

    def mock_get_settings_for_client():
        s = Settings()
        s.DEMO_MODE = run_in_demo_mode
        s.RUN_ALEMBIC_ON_STARTUP = False
        return s

    monkeypatch.setattr("app.main.get_settings", mock_get_settings_for_client)
    monkeypatch.setattr("app.core.settings.get_settings", mock_get_settings_for_client)

    test_app = create_app()

    if original_env_file is not None:
        Settings.model_config["env_file"] = original_env_file
    else:
        if "env_file" in Settings.model_config:
            del Settings.model_config["env_file"]
    get_settings.cache_clear()

    AppTestSessionMaker = AsyncSessionMaker.__class__(bind=test_engine, expire_on_commit=False)

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with AppTestSessionMaker() as session:
            yield session

    test_app.dependency_overrides[get_async_session] = override_get_async_session
    return TestClient(test_app)
