# tests/conftest.py
# Full file content
import asyncio
import logging
import os
from typing import AsyncGenerator, Generator

import pytest
from alembic.command import upgrade
from alembic.config import Config as AlembicConfig
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.api.chat  # Import module to access original cfg
import app.core.settings as core_settings_module
import app.db.session as db_session_module
import app.main as main_module

# Ensure this import uses the corrected Settings class
from app.core.settings import Settings, get_settings
from app.db.session import get_async_session
from app.main import app as fastapi_app  # Import the app instance for client

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mock_settings() -> Settings:
    """
    Creates a Settings instance for testing, overriding .env file loading
    and using test-specific RAG namespaces.
    """
    # For Pydantic V2 BaseSettings, pass _env_file=None to prevent .env loading
    # and set other fields directly or let them take defaults.
    mock_settings = Settings(
        _env_file=None,  # This prevents loading any .env file for this instance
        CHROMA_NAMESPACE_THEORY="theory_test_conftest",
        CHROMA_NAMESPACE_PERSONAL_PLAN="personal_plan_test_conftest",
        CHROMA_NAMESPACE_SESSION_DATA="session_data_test_conftest",
        CHROMA_NAMESPACE_FUTURE_ME="future_me_test_conftest",
        CHROMA_NAMESPACE_THERAPIST_NOTES="therapist_notes_test_conftest",
        CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES="dfm_chat_history_summaries_test_conftest",
        CHROMA_HOST=None,  # Ensure tests use local Chroma
        CHROMA_PORT=None,  # Ensure tests use local Chroma
        DATABASE_URL=os.getenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///./test.db"),  # Ensure test DB is used
        OPENAI_API_KEY="test_openai_api_key_for_pytest",  # Use a consistent test key
    )
    return mock_settings


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def _prepare_test_db_file(test_db_url: str):
    if "sqlite" in test_db_url:
        db_file = test_db_url.split("///")[-1]
        if os.path.exists(db_file):
            logger.info(f"Deleting existing test database file: {db_file}")
            os.remove(db_file)


@pytest.fixture(scope="session", autouse=True)
def session_setup_and_migrations():  # No monkeypatch fixture requested
    """
    Handles all session-wide setup:
    1. Mocks global application settings.
    Applies Alembic migrations to the test database at the start of the session.
    """
    logger.info("Applying session_setup_and_migrations fixture")

    # Manually save original objects/functions to restore later
    original_core_get_settings = core_settings_module.get_settings
    original_db_session_get_settings = db_session_module.get_settings
    original_main_get_settings = main_module.get_settings  # If get_settings is in app.main
    original_chat_cfg = app.api.chat.cfg  # Assuming chat.py imports cfg directly

    # 1. Mock global settings
    mocked_settings_instance = create_mock_settings()

    def mock_get_settings_func() -> Settings:
        return mocked_settings_instance

    # Manually patch the objects/functions
    core_settings_module.get_settings = mock_get_settings_func
    db_session_module.get_settings = mock_get_settings_func
    main_module.get_settings = mock_get_settings_func  # If get_settings is in app.main
    app.api.chat.cfg = mocked_settings_instance  # Patch the imported cfg

    # Add more manual patches here if needed for other modules importing settings
    # e.g., original_some_module_cfg = app.some_module.cfg
    #       app.some_module.cfg = mocked_settings_instance

    test_db_url = mocked_settings_instance.DATABASE_URL  # Use the mocked URL

    logger.info(f"Preparing test database with URL: {test_db_url}")
    _prepare_test_db_file(test_db_url)

    logger.info("Running Alembic migrations synchronously to prepare test DB...")
    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    alembic_cfg.set_main_option("script_location", "app/db/migrations")

    try:
        upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations completed successfully.")
    except Exception as e:
        logger.error(f"Error during Alembic migrations: {e}")
        raise

    # Yield to signal setup is complete and run tests
    yield

    # Teardown: Restore original objects/functions
    logger.info("Tearing down session_setup_and_migrations fixture: Restoring original settings")
    core_settings_module.get_settings = original_core_get_settings
    db_session_module.get_settings = original_db_session_get_settings
    main_module.get_settings = original_main_get_settings  # If get_settings is in app.main
    app.api.chat.cfg = original_chat_cfg


@pytest.fixture(scope="session")
async def test_engine(session_setup_and_migrations: None):  # Depends on the combined setup
    """
    Provides an async SQLAlchemy engine for the test session.
    Depends on apply_migrations_to_test_db.
    """
    settings = get_settings()  # Gets mocked settings
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG_SQL,
        connect_args={"timeout": 20} if "sqlite" in settings.DATABASE_URL else {},
    )
    logger.info(f"Created test engine for {settings.DATABASE_URL} with connect_args: {engine.connect_args}")
    yield engine
    logger.info("Disposing test engine.")
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an async SQLAlchemy session for each test function.
    Ensures transactions are rolled back after each test.
    """
    AsyncScopedSession = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with AsyncScopedSession() as session:
        await session.begin_nested()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.rollback()
            await session.close()


@pytest.fixture(scope="session")
def client(
    session_setup_and_migrations: None, event_loop: asyncio.AbstractEventLoop
) -> Generator[TestClient, None, None]:
    """
    Provides a TestClient for making API requests.
    Depends on session_setup_and_migrations to ensure settings are mocked and DB is ready.
    """
    # Settings are mocked by session_setup_and_migrations (autouse)
    # app = create_app() # create_app might re-evaluate settings if not careful

    async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
        settings = get_settings()
        engine = create_async_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG_SQL,
            connect_args={"timeout": 20} if "sqlite" in settings.DATABASE_URL else {},
        )
        LocalAsyncSession = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with LocalAsyncSession() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        await engine.dispose()

    fastapi_app.dependency_overrides[get_async_session] = override_get_async_session

    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture
def temp_prompt_files(tmp_path, session_setup_and_migrations):  # Depends on session_setup to get mocked settings
    """
    Creates temporary prompt files for testing.
    Uses tmp_path for function scope, ensuring settings are mocked before accessing them.
    Note: If you need session-scoped prompt files, use tmp_path_factory and scope="session".
    For now, keeping it function-scoped as it's simpler with tmp_path.
    """
    settings = get_settings()  # Get the mocked settings
    prompt_dir = tmp_path / settings.PROMPT_TEMPLATE_DIR
    prompt_dir.mkdir(parents=True, exist_ok=True)

    (prompt_dir / settings.SYSTEM_PROMPT_FILE).write_text(
        "System: You are a helpful AI. Context: {context} User: {question} User Data: {user_data}"
    )
    (prompt_dir / settings.CRISIS_PROMPT_FILE).write_text(
        "Crisis: Respond with empathy. Context: {context} User: {question} User Data: {user_data}"
    )

    original_prompt_dir = settings.PROMPT_TEMPLATE_DIR
    settings.PROMPT_TEMPLATE_DIR = str(prompt_dir)  # Use the string path
    yield str(prompt_dir)  # Provide the path if needed
    settings.PROMPT_TEMPLATE_DIR = original_prompt_dir
    # shutil.rmtree(prompt_dir_str) # tmp_path handles cleanup
