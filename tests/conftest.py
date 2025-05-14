# /home/dfront/code/dear_future_me/tests/conftest.py
import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import text  # For debug query
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

import app.auth.models as auth_models_module  # The module for UserTable
import app.db.models.user_profile as user_profile_models_module  # The module for UserProfileTable

# For debugging Base instances:
import app.db.session as session_module  # The module where Base is defined
from app.core.settings import get_settings

# 1. Import Base first. This is the declarative base all models should use.
#    Alias it to ConftestBase for clarity in debug messages.
from app.db.session import Base as ConftestBase
from app.db.session import get_async_session
from app.main import app as fastapi_application_instance

# 2. Then, import the model classes. This ensures they register with the `Base` imported above.


settings = get_settings()

TEST_DB_PATH = "./test_app_super_debug.db"  # Using an even more distinct name
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH}"


engine_test = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
AsyncSessionLocalTest = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)


async def override_get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocalTest() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


fastapi_application_instance.dependency_overrides[get_async_session] = override_get_async_session


@pytest.fixture(scope="session")
def event_loop(request) -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def _bootstrap_db(event_loop: asyncio.AbstractEventLoop):
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

    # --- Debugging Base instances ---
    print(f"DEBUG [conftest.py]: id(ConftestBase) from app.db.session (imported as ConftestBase): {id(ConftestBase)}")
    print(
        f"DEBUG [conftest.py]: id(session_module.Base) (direct import of app.db.session.Base): {id(session_module.Base)}"
    )

    # Check the Base instance that the UserTable class is actually using.
    # This relies on the print statement in app.auth.models
    # We also check if the 'Base' attribute of the imported module is the same.
    if hasattr(auth_models_module, "Base"):
        print(
            f"DEBUG [conftest.py]: id(auth_models_module.Base) (Base from app.auth.models): {id(auth_models_module.Base)}"
        )
        if id(ConftestBase) != id(auth_models_module.Base):
            print("CRITICAL DEBUG [conftest.py]: ConftestBase is NOT the same instance as auth_models_module.Base!")
    else:
        print("DEBUG [conftest.py]: auth_models_module does not have a 'Base' attribute directly.")

    if hasattr(user_profile_models_module, "Base"):
        print(
            f"DEBUG [conftest.py]: id(user_profile_models_module.Base) (Base from app.db.models.user_profile): {id(user_profile_models_module.Base)}"
        )
        if id(ConftestBase) != id(user_profile_models_module.Base):
            print(
                "CRITICAL DEBUG [conftest.py]: ConftestBase is NOT the same instance as user_profile_models_module.Base!"
            )
    else:
        print("DEBUG [conftest.py]: user_profile_models_module does not have a 'Base' attribute directly.")
    # --- End Debugging Base instances ---

    # --- Debugging: Check tables known to Base.metadata ---
    known_tables_before = list(ConftestBase.metadata.tables.keys())
    print(f"DEBUG [conftest.py]: Tables known to ConftestBase.metadata BEFORE create_all: {known_tables_before}")
    if "user" not in known_tables_before:
        print("DEBUG [conftest.py]: CRITICAL - 'user' table NOT known to ConftestBase.metadata before create_all.")
    if "user_profile" not in known_tables_before:
        print(
            "DEBUG [conftest.py]: CRITICAL - 'user_profile' table NOT known to ConftestBase.metadata before create_all."
        )
    # --- End Debugging ---

    async with engine_test.begin() as conn:
        await conn.run_sync(ConftestBase.metadata.drop_all)
        await conn.run_sync(ConftestBase.metadata.create_all)

    # --- Debugging: Check tables after creation and via direct SQL ---
    known_tables_after = list(ConftestBase.metadata.tables.keys())
    print(f"DEBUG [conftest.py]: Tables known to ConftestBase.metadata AFTER create_all: {known_tables_after}")

    async with AsyncSessionLocalTest() as temp_session:
        try:
            result_user = await temp_session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='user';")
            )
            if result_user.scalar_one_or_none():
                print("DEBUG [conftest.py]: 'user' table confirmed to exist via direct SQL query.")
            else:
                print("DEBUG [conftest.py]: 'user' table DOES NOT EXIST via direct SQL query.")
        except Exception as e:
            print(f"DEBUG [conftest.py]: Error checking 'user' table via SQL: {e}")
        try:
            result_profile = await temp_session.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_profile';")
            )
            if result_profile.scalar_one_or_none():
                print("DEBUG [conftest.py]: 'user_profile' table confirmed to exist via direct SQL query.")
            else:
                print("DEBUG [conftest.py]: 'user_profile' table DOES NOT EXIST via direct SQL query.")
        except Exception as e:
            print(f"DEBUG [conftest.py]: Error checking 'user_profile' table via SQL: {e}")
    # --- End Debugging ---

    yield

    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


@pytest_asyncio.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocalTest() as session:
        async with session.begin_nested() as nested_transaction:
            yield session
            await nested_transaction.rollback()


@pytest.fixture(scope="function")
def client(event_loop: asyncio.AbstractEventLoop) -> Generator[TestClient, None, None]:
    with TestClient(fastapi_application_instance) as c:
        yield c
