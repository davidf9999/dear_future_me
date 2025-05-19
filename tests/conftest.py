# /home/dfront/code/dear_future_me/tests/conftest.py
# ruff: noqa: E402
"""
Global test fixtures.
"""

import os
from typing import AsyncGenerator, Optional

import pytest
import pytest_asyncio
from alembic import command as alembic_command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as create_sync_engine_sa
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

from app.auth.models import Base, SafetyPlanTable, UserProfileTable, UserTable
from app.core import settings as core_settings_module
from app.core.settings import Settings, get_settings
from app.db.session import get_async_session
from app.main import create_app


def create_mock_settings(
    lang: str = "en",
    openai_key: Optional[str] = "test_openai_key_conftest",
    llm_model: str = "test_model_conftest",
    chroma_dir: str = "/tmp/test_chroma_conftest",
    chroma_host: Optional[str] = None,
    chroma_port: Optional[int] = None,
) -> Settings:
    mock_settings = Settings(_model_config={"env_file": None})
    mock_settings.APP_DEFAULT_LANGUAGE = lang
    mock_settings.OPENAI_API_KEY = openai_key
    mock_settings.LLM_MODEL = llm_model
    mock_settings.PROMPT_TEMPLATE_DIR = "templates"
    mock_settings.CRISIS_PROMPT_FILE = "crisis_prompt.md"
    mock_settings.SYSTEM_PROMPT_FILE = "system_prompt.md"
    mock_settings.CHROMA_DIR = chroma_dir
    mock_settings.CHROMA_HOST = chroma_host
    mock_settings.CHROMA_PORT = chroma_port
    mock_settings.CHROMA_NAMESPACE_THEORY = "theory_test_conftest"
    mock_settings.CHROMA_NAMESPACE_PERSONAL_PLAN = "personal_plan_test_conftest"
    mock_settings.CHROMA_NAMESPACE_SESSION_DATA = "session_data_test_conftest"
    mock_settings.CHROMA_NAMESPACE_FUTURE_ME = "future_me_test_conftest"
    mock_settings.CHROMA_NAMESPACE_THERAPIST_NOTES = "therapist_notes_test_conftest"
    mock_settings.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES = "dfm_chat_history_summaries_test_conftest"
    return mock_settings


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db_file() -> None:
    core_settings_module._settings_instance = None
    settings = get_settings()
    db_url = settings.DATABASE_URL
    db_file_path = None

    if db_url.startswith("sqlite+aiosqlite:///"):
        db_file_path = db_url.replace("sqlite+aiosqlite:///", "")
        if db_file_path == ":memory:":
            print("INFO (_prepare_test_db_file): Using in-memory SQLite for tests.")
        elif os.path.exists(db_file_path):
            print(f"INFO (_prepare_test_db_file): Deleting existing test database file: {db_file_path}")
            try:
                os.remove(db_file_path)
            except OSError as e:
                print(f"WARNING (_prepare_test_db_file): Could not delete {db_file_path}: {e}")

    print("INFO (_prepare_test_db_file): Running Alembic migrations synchronously to prepare test DB...")
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", str(db_url))

    try:
        alembic_command.upgrade(alembic_cfg, "head")
        print("INFO (_prepare_test_db_file): Alembic migrations completed successfully.")
    except Exception as e_alembic:
        print(f"CRITICAL ERROR (_prepare_test_db_file): Alembic upgrade FAILED: {e_alembic}")
        raise RuntimeError(f"Alembic migrations failed: {e_alembic}") from e_alembic

    if db_file_path and db_file_path != ":memory:":
        print("INFO (_prepare_test_db_file): Synchronously verifying table creation after Alembic...")
        sync_db_url_for_verify = str(db_url).replace("sqlite+aiosqlite:///", "sqlite:///")
        sync_engine_verify = create_sync_engine_sa(sync_db_url_for_verify)
        try:
            with sync_engine_verify.connect() as conn_verify:
                inspector = sqlalchemy_inspect(conn_verify)
                all_tables_in_metadata = Base.metadata.tables.keys()
                all_exist = True
                for table_name_key in all_tables_in_metadata:
                    table_obj = Base.metadata.tables[table_name_key]
                    if not inspector.has_table(table_obj.name):
                        print(f"ERROR (_prepare_test_db_file): Table '{table_obj.name}' NOT FOUND.")
                        all_exist = False
                    else:
                        print(f"INFO (_prepare_test_db_file): Table '{table_obj.name}' FOUND.")
                if not all_exist:
                    raise RuntimeError("Schema verification failed: Not all tables created by Alembic.")
            print("INFO (_prepare_test_db_file): Synchronous table verification successful.")
        finally:
            sync_engine_verify.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_engine(_prepare_test_db_file) -> AsyncGenerator[AsyncEngine, None]:
    core_settings_module._settings_instance = None
    settings = get_settings()
    connect_args = {"timeout": 20} if "sqlite" in settings.DATABASE_URL else {}
    engine = create_async_engine(
        settings.DATABASE_URL, echo=settings.DEBUG_SQL, connect_args=connect_args, pool_recycle=3600
    )
    print(f"INFO (test_engine): Created test engine for {settings.DATABASE_URL} with connect_args: {connect_args}")
    try:
        yield engine
    finally:
        print("INFO (test_engine): Disposing test engine.")
        await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provides a transactional scope for tests needing direct DB access."""
    async with test_engine.connect() as connection:
        async with connection.begin() as transaction:
            session = AsyncSession(bind=connection, expire_on_commit=False)
            # print(f"INFO (db_session): Created session {id(session)} within transaction {id(transaction)} on connection {id(connection)}.")
            try:
                yield session
                await transaction.commit()
                # print(f"INFO (db_session): Committed transaction {id(transaction)} for session {id(session)}.")
            except Exception:
                await transaction.rollback()
                # print(f"ERROR (db_session): Exception in test, rolled back transaction {id(transaction)} for session {id(session)}.")
                raise
            finally:
                await session.close()
                # print(f"INFO (db_session): Closed session {id(session)}.")
        # print(f"INFO (db_session): Connection {id(connection)} released by test_engine.connect() context manager.")


@pytest_asyncio.fixture(autouse=True)
async def clear_tables_before_test(test_engine: AsyncEngine) -> None:
    """Clears all data from user-managed tables before each test, using its own connection."""
    tables_to_clear = [SafetyPlanTable.__tablename__, UserProfileTable.__tablename__, UserTable.__tablename__]

    # Use a new connection for this operation to ensure isolation
    async with test_engine.connect() as conn:
        async with conn.begin():  # Start a transaction
            for table_name in tables_to_clear:
                # Check existence using run_sync
                def check_exists_sync(s_conn, t_name):
                    return sqlalchemy_inspect(s_conn).has_table(t_name)

                exists = await conn.run_sync(check_exists_sync, table_name)

                if exists:
                    await conn.execute(text(f"DELETE FROM {table_name}"))
                    # print(f"INFO (clear_tables_before_test): Cleared table {table_name}.")
                # else:
                # print(f"INFO (clear_tables_before_test): Table {table_name} does not exist, skipping.")
        # Transaction is committed here if no exceptions, or rolled back otherwise.
    # Connection is closed here.


@pytest.fixture(scope="function")
def client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, test_engine: AsyncEngine) -> TestClient:
    core_settings_module._settings_instance = None

    mock_settings_for_app = create_mock_settings()

    marker = request.node.get_closest_marker("demo_mode")
    if marker and marker.args and marker.args[0] is False:
        mock_settings_for_app.DEMO_MODE = False

    mock_settings_for_app.RUN_ALEMBIC_ON_STARTUP = False
    mock_settings_for_app.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "test_client_mock_key")

    modules_to_patch_settings = [
        "app.main",
        "app.core.settings",
        "app.api.orchestrator",
        "app.rag.processor",
        "app.db.migrate",
    ]
    for module_name in modules_to_patch_settings:
        try:
            module = __import__(module_name, fromlist=["get_settings", "cfg"])
            if hasattr(module, "get_settings"):
                monkeypatch.setattr(f"{module_name}.get_settings", lambda: mock_settings_for_app)
            if hasattr(module, "cfg"):
                monkeypatch.setattr(f"{module_name}.cfg", mock_settings_for_app)
        except ImportError:
            print(f"Warning: Module {module_name} not found for settings patching.")
        except AttributeError:
            pass

    test_app = create_app()

    async def override_get_async_session_for_client() -> AsyncGenerator[AsyncSession, None]:
        async with test_engine.connect() as connection:
            async with connection.begin() as transaction:
                session = AsyncSession(bind=connection, expire_on_commit=False)
                # print(f"INFO (override_get_async_session): Created session {id(session)} for TestClient request.")
                try:
                    yield session
                    await transaction.commit()
                    # print(f"INFO (override_get_async_session): Committed transaction {id(transaction)}.")
                except Exception:
                    await transaction.rollback()
                    # print(f"ERROR (override_get_async_session): Exception in request, rolled back transaction {id(transaction)}.")
                    raise
                finally:
                    await session.close()
                    # print(f"INFO (override_get_async_session): Closed session {id(session)}.")
            # print(f"INFO (override_get_async_session): Connection {id(connection)} released by test_engine.connect() context manager.")

    test_app.dependency_overrides[get_async_session] = override_get_async_session_for_client

    try:
        yield TestClient(test_app)
    finally:
        core_settings_module._settings_instance = None
        test_app.dependency_overrides.clear()
