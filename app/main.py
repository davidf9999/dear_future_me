# app/main.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator  # Add this import

from fastapi import Depends, FastAPI
from fastapi_users.exceptions import UserNotExists

from app.api.chat import router as chat_router
from app.api.rag import RagOrchestrator
from app.api.rag import router as rag_router
from app.auth.router import (
    UserManager,
    auth_router,
    fastapi_users,
    get_user_db,
    register_router,
)
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.core.settings import Settings, get_settings  # Import Settings as well
from app.db.init_db import init_db
from app.db.migrate import upgrade_head
from app.db.session import engine, get_async_session


# Lifespan function now takes settings as an argument
@asynccontextmanager
async def lifespan(app: FastAPI, app_settings: Settings) -> AsyncGenerator[None, None]:  # Add app_settings parameter
    if app_settings.DEMO_MODE:  # Use app_settings
        print("INFO: DEMO_MODE is active. Initializing database (dropping and recreating tables)...")
        await init_db()

        if app_settings.DEMO_USER_EMAIL and app_settings.DEMO_USER_PASSWORD:
            print(f"INFO: DEMO_MODE - Attempting to set up demo user: {app_settings.DEMO_USER_EMAIL}")
            try:
                async for session in get_async_session():
                    user_db_instance = None
                    async for udb in get_user_db(session):
                        user_db_instance = udb
                        break
                    if user_db_instance:
                        user_manager_instance = UserManager(user_db_instance)
                        try:
                            await user_manager_instance.get_by_email(app_settings.DEMO_USER_EMAIL)
                            # If get_by_email returns a user object, it means the user exists.
                            # fastapi-users' get_by_email raises UserNotExists if not found.
                            print(f"INFO: DEMO_MODE - Demo user '{app_settings.DEMO_USER_EMAIL}' already exists.")
                        except UserNotExists:
                            print(
                                f"INFO: DEMO_MODE - Demo user '{app_settings.DEMO_USER_EMAIL}' not found. Creating..."
                            )
                            user_create_schema = UserCreate(
                                email=app_settings.DEMO_USER_EMAIL,
                                password=app_settings.DEMO_USER_PASSWORD,
                                is_active=True,
                            )
                            await user_manager_instance.create(user_create_schema, safe=True)
                            print(f"INFO: DEMO_MODE - Demo user '{app_settings.DEMO_USER_EMAIL}' created successfully.")

                    else:
                        print("ERROR: DEMO_MODE - Could not obtain UserDatabase instance to create demo user.")
            except Exception as e:
                # Catch any other exceptions during the setup process
                print(f"ERROR: DEMO_MODE - An error occurred during demo user setup: {e}")
                import traceback

                traceback.print_exc()  # For more detailed error logging
    else:
        print("INFO: DEMO_MODE is false. Applying Alembic migrations if any...")
        try:
            upgrade_head()
            print("INFO: Alembic migrations applied successfully (or already up-to-date).")
        except Exception as exc:
            print(f"ERROR: Alembic upgrade failed: {exc}")
            raise RuntimeError(f"Alembic upgrade failed: {exc}") from exc

    print("INFO: Initializing RagOrchestrator...")
    # If RagOrchestrator needs settings, it should ideally get them internally
    # or have them passed during instantiation if they can vary per app instance.
    app.state.rag_orchestrator = RagOrchestrator()
    print("INFO: RagOrchestrator initialized.")

    yield

    print("INFO: Application shutting down. Disposing database engine...")
    await engine.dispose()
    print("INFO: Database engine disposed.")


def create_app() -> FastAPI:
    # Fetch settings inside the factory, after env vars might have been patched
    app_settings = get_settings()

    # Define lifespan_wrapper to pass settings
    @asynccontextmanager
    async def lifespan_wrapper(app_instance: FastAPI) -> AsyncGenerator[None, None]:
        # Correctly enter the context of the main lifespan function
        # The 'lifespan' function is an async context manager, so use 'async with'.
        async with lifespan(app_instance, app_settings):
            yield
        # The cleanup part of 'lifespan' will execute when this 'async with' block exits.

    instance = FastAPI(title="Dear Future Me API", lifespan=lifespan_wrapper)

    # It's generally safer if fastapi_users and current_active_user are also
    # initialized within create_app if their behavior depends on settings
    # that might change per app instance (e.g., for testing).
    # For now, we assume the globally imported fastapi_users from router.py is sufficient.
    # If SECRET_KEY or other auth-related settings were dynamic per test,
    # the FastAPIUsers instance and its components (like JWTStrategy) would need
    # to be created here, using the app_settings.
    current_active_user = fastapi_users.current_user(active=True)

    # Auth endpoints - Conditionally include registration router
    if not app_settings.DEMO_MODE:  # Use app_settings
        instance.include_router(register_router, prefix="/auth", tags=["auth"])
        print("INFO: Standard mode - Registration router enabled.")
    else:
        print("INFO: DEMO_MODE is active - Registration router is disabled.")

    instance.include_router(auth_router, prefix="/auth", tags=["auth"])
    instance.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/users",
        tags=["users"],
    )

    # # Chat endpoints - ALWAYS protected
    # instance.include_router(chat_router, dependencies=[Depends(current_active_user)])
    # or
    # Chat endpoints - Conditionally protected
    chat_dependencies = []
    if not app_settings.SKIP_AUTH:
        chat_dependencies.append(Depends(current_active_user))
        print("INFO: SKIP_AUTH is false. Chat endpoints are protected.")
    else:
        print("INFO: SKIP_AUTH is true. Chat endpoints are NOT protected (authentication bypassed).")
    instance.include_router(chat_router, dependencies=chat_dependencies)

    # RAG endpoints
    instance.include_router(rag_router)

    # Health check
    @instance.get("/ping", tags=["health"])
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}

    return instance


# Global app instance for Uvicorn, but tests will use create_app()
app = create_app()
