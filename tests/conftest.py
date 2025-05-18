# /home/dfront/code/dear_future_me/tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

import os  # For os.remove if needed
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import Session as SyncSession

# Ensure all models are imported before Base.metadata is used by drop_all or migrations
from app.auth.models import Base, SafetyPlanTable, UserProfileTable, UserTable
from app.core.settings import Settings, get_settings

# Import AsyncSessionMaker class
from app.db.session import get_async_session  # Ensure AsyncSessionMaker is imported

# Import the factory function instead of the global app instance
from app.main import create_app

# pytest-asyncio's event_loop fixture will now be session-scoped due to pytest.ini setting.


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db_file() -> None:
    """
    Synchronously prepares the test database file *before* the async test engine is created.
    1. Deletes the old test.db file if it exists.
    2. Runs Alembic migrations synchronously to create the schema.
    """
    settings = get_settings()
    db_url = settings.DATABASE_URL
    db_file_path = None

    if db_url.startswith("sqlite+aiosqlite:///"):
        db_file_path = db_url.replace("sqlite+aiosqlite:///", "")
        if db_file_path == ":memory:":
            print("INFO (_prepare_test_db_file): Using in-memory SQLite. Alembic will run on a temporary in-memory DB.")
        elif os.path.exists(db_file_path):
            print(f"INFO (_prepare_test_db_file): Deleting existing test database file: {db_file_path}")
            try:
                os.remove(db_file_path)
            except OSError as e:
                print(f"WARNING (_prepare_test_db_file): Could not delete {db_file_path}: {e}")

    print("INFO (_prepare_test_db_file): Running Alembic migrations synchronously to prepare test DB...")
    alembic_cfg = Config("alembic.ini")
    # For synchronous Alembic run, ensure it uses a synchronous DB URL if env.py expects it.
    # However, our env.py is designed to handle async URL for CLI mode by creating an async engine.
    # So, passing the async URL should be fine.
    alembic_cfg.set_main_option("sqlalchemy.url", str(db_url))

    try:
        alembic_command.upgrade(alembic_cfg, "head")
        print("INFO (_prepare_test_db_file): Alembic migrations completed successfully.")
    except Exception as e_alembic:
        print(f"CRITICAL ERROR (_prepare_test_db_file): Alembic upgrade FAILED: {e_alembic}")
        raise RuntimeError(f"Alembic migrations failed during synchronous pre-test setup: {e_alembic}") from e_alembic

    if db_file_path and db_file_path != ":memory:":
        print("INFO (_prepare_test_db_file): Synchronously verifying table creation...")
        sync_db_url_for_verify = db_url.replace("sqlite+aiosqlite:///", "sqlite:///")
        sync_engine_verify = create_sync_engine(sync_db_url_for_verify)
        try:
            with SyncSession(sync_engine_verify) as _sync_session_verify:  # Use SyncSession, variable prefixed with _
                inspector = inspect(sync_engine_verify)
                all_tables_in_metadata = Base.metadata.tables.keys()
                all_exist = True
                for table_name_key in all_tables_in_metadata:
                    table_obj = Base.metadata.tables[table_name_key]
                    if not inspector.has_table(table_obj.name):
                        print(
                            f"ERROR (_prepare_test_db_file): Table '{table_obj.name}' NOT FOUND after sync Alembic run."
                        )
                        all_exist = False
                    else:
                        print(f"INFO (_prepare_test_db_file): Table '{table_obj.name}' FOUND after sync Alembic run.")
                if not all_exist:
                    raise RuntimeError(
                        "Schema verification failed after synchronous Alembic upgrade: Not all tables created."
                    )
            print("INFO (_prepare_test_db_file): Synchronous table verification successful.")
        finally:
            sync_engine_verify.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_engine(_prepare_test_db_file) -> AsyncGenerator[AsyncEngine, None]:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG_SQL)
    print(f"INFO (test_engine): Created test engine for {settings.DATABASE_URL} (after sync Alembic setup)")
    yield engine
    print("INFO (test_engine): Disposing test engine.")
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_db_connection_scoped(test_engine: AsyncEngine) -> AsyncGenerator[AsyncConnection, None]:
    print("INFO (test_db_connection_scoped): Acquiring session-scoped connection.")
    async with test_engine.connect() as connection:
        async with connection.begin() as transaction:
            print("INFO (test_db_connection_scoped): Started transaction for session-scoped connection.")
            yield connection
            print("INFO (test_db_connection_scoped): Rolling back transaction for session-scoped connection.")
            await transaction.rollback()
    print("INFO (test_db_connection_scoped): Session-scoped connection released.")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_db(test_engine: AsyncEngine, test_db_connection_scoped: AsyncConnection) -> None:
    _ = UserTable
    _ = UserProfileTable
    _ = SafetyPlanTable

    conn_for_check = test_db_connection_scoped

    print("INFO (_bootstrap_db): Verifying table existence using session-scoped connection...")
    # Use begin_nested if already in transaction, else begin.
    # The test_db_connection_scoped already yields a connection within a transaction.
    # So, operations on conn_for_check are already within that transaction.
    # A nested transaction is appropriate here for the verification block.
    async with conn_for_check.begin_nested() as _verification_transaction:  # Variable prefixed with _
        all_tables_in_metadata = Base.metadata.tables.keys()
        all_exist_and_accounted_for = True
        for table_name_key in all_tables_in_metadata:
            table_obj = Base.metadata.tables[table_name_key]

            def sync_check_final(conn_sync_final, name_sync_final):
                inspector = inspect(conn_sync_final)
                return inspector.has_table(name_sync_final)

            exists = await conn_for_check.run_sync(sync_check_final, table_obj.name)
            print(f"INFO (_bootstrap_db final check): Table '{table_obj.name}' exists: {exists}")
            if not exists:
                all_exist_and_accounted_for = False
        if not all_exist_and_accounted_for:
            # No need to explicitly rollback verification_transaction if error, outer will handle.
            print("CRITICAL ERROR (_bootstrap_db): Not all expected tables exist after Alembic migrations.")
            raise RuntimeError("Schema verification failed: Not all tables created by Alembic.")
        else:
            print("INFO (_bootstrap_db): All expected tables confirmed to exist.")
            # No explicit commit for verification_transaction, it's part of the larger scope.
    print("INFO (_bootstrap_db): Test database schema verification completed.")


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a SQLAlchemy AsyncSession for each test function, using the main test_engine.
    Each test gets its own session and transaction.
    """
    async with test_engine.connect() as connection:  # New connection per test
        async with connection.begin() as transaction:  # New transaction per test
            # Create session bound to this specific connection
            session = AsyncSession(bind=connection, expire_on_commit=False)
            print(
                f"INFO (db_session): Created new session {session} for test on connection {connection} within transaction {transaction}."
            )
            yield session
            print(f"INFO (db_session): Rolling back transaction {transaction} for test session {session}.")
            # Transaction is rolled back by the 'async with connection.begin()' context manager
    print("INFO (db_session): Connection for test session released.")


@pytest_asyncio.fixture(autouse=True)
async def clear_tables_before_test(db_session: AsyncSession) -> None:
    """
    Ensures relevant tables are empty before each test.
    Uses the function-scoped session.
    """
    _ = UserTable
    _ = UserProfileTable
    _ = SafetyPlanTable

    tables_to_clear = [SafetyPlanTable, UserProfileTable, UserTable]
    for table in tables_to_clear:
        try:
            # The db_session.run_sync will provide the sync connection to the lambda
            if await db_session.run_sync(lambda sync_conn: inspect(sync_conn).has_table(table.__tablename__)):
                await db_session.execute(text(f"DELETE FROM {table.__tablename__}"))
            else:
                print(f"INFO (clear_tables_before_test): Table {table.__tablename__} does not exist, skipping delete.")
        except Exception as e:
            print(f"WARNING (clear_tables_before_test): Could not clear table {table.__tablename__}: {e}.")
    await db_session.commit()  # Commit the DELETE operations


@pytest.fixture(scope="function")
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine) -> TestClient:
    """
    Provides a TestClient instance for FastAPI.
    The dependency override for get_async_session will use the test_engine.
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
    monkeypatch.setattr("app.db.migrate.get_settings", mock_get_settings_for_client)

    test_app = create_app()

    async def override_get_async_session_for_client() -> AsyncGenerator[AsyncSession, None]:
        # Each request gets a new connection and transaction from the engine
        async with test_engine.connect() as connection:
            async with connection.begin() as transaction:
                session = AsyncSession(bind=connection, expire_on_commit=False)
                print(
                    f"INFO (override_get_async_session_for_client): Providing session {session} for TestClient request on connection {connection} within transaction {transaction}."
                )
                try:
                    yield session
                finally:
                    print(
                        f"INFO (override_get_async_session_for_client): TestClient request session {session} transaction ending (auto-managed)."
                    )

    test_app.dependency_overrides[get_async_session] = override_get_async_session_for_client

    if original_env_file is not None:
        Settings.model_config["env_file"] = original_env_file
    else:
        if "env_file" in Settings.model_config:
            del Settings.model_config["env_file"]
    get_settings.cache_clear()

    return TestClient(test_app)
