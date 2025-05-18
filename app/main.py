# app/main.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI
from fastapi_users.exceptions import UserNotExists
from sqlalchemy.ext.asyncio import create_async_engine  # Added import

from app.api.chat import router as chat_router
from app.api.rag import RagOrchestrator
from app.api.rag import router as rag_router
from app.auth.models import Base  # Added import
from app.auth.router import (
    UserManager,
    auth_router,
    fastapi_users,
    get_user_db,
    register_router,
)
from app.auth.schemas import UserCreate, UserRead, UserUpdate
from app.core.settings import Settings, get_settings

# app.db.init_db is no longer used directly for table creation in lifespan
from app.db.migrate import upgrade_head
from app.db.session import (
    engine as global_engine,  # Renamed to avoid clash with local engine
)
from app.db.session import get_async_session


# Lifespan function now takes settings as an argument
@asynccontextmanager
async def lifespan(app: FastAPI, app_settings: Settings) -> AsyncGenerator[None, None]:
    if app_settings.DEMO_MODE:
        # ... (demo mode logic remains the same) ...
        print(
            "INFO: DEMO_MODE is active. Initializing database (dropping and recreating tables directly from models)..."
        )
        demo_engine = create_async_engine(app_settings.DATABASE_URL, echo=app_settings.DEBUG_SQL)
        async with demo_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await demo_engine.dispose()
        print("INFO: DEMO_MODE - Database dropped and recreated from models.")

        if not app_settings.SKIP_AUTH and app_settings.DEMO_USER_EMAIL and app_settings.DEMO_USER_PASSWORD:
            # ... (demo user creation logic remains the same) ...
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
                    break
            except Exception as e:
                print(f"ERROR: DEMO_MODE - An error occurred during demo user setup: {e}")
                import traceback

                traceback.print_exc()
        elif app_settings.SKIP_AUTH:
            print("INFO: DEMO_MODE is active, but SKIP_AUTH is true. Skipping demo user creation.")
        else:
            print(
                "INFO: DEMO_MODE is active, but demo user credentials are not fully set. Skipping demo user creation."
            )
    else:  # NOT DEMO_MODE
        if app_settings.RUN_ALEMBIC_ON_STARTUP:  # Check the new setting
            print("INFO: RUN_ALEMBIC_ON_STARTUP is true. Applying Alembic migrations (during app startup)...")
            try:
                upgrade_head()
                print("INFO: Alembic migrations applied successfully (or already up-to-date during app startup).")
            except Exception as exc:
                print(f"ERROR: Alembic upgrade failed during app startup: {exc}")
                raise RuntimeError(f"Alembic upgrade failed during app startup: {exc}") from exc
        else:
            print(
                "INFO: RUN_ALEMBIC_ON_STARTUP is false. Skipping Alembic migrations during app startup (expected for tests)."
            )

    print("INFO: Initializing RagOrchestrator...")
    app.state.rag_orchestrator = RagOrchestrator()
    print("INFO: RagOrchestrator initialized.")

    yield

    print("INFO: Application shutting down. Disposing global database engine...")
    await global_engine.dispose()
    print("INFO: Global database engine disposed.")


# ... (create_app and global app instance remain the same) ...
def create_app() -> FastAPI:
    app_settings = get_settings()  # get_settings() will now load RUN_ALEMBIC_ON_STARTUP

    @asynccontextmanager
    async def lifespan_wrapper(app_instance: FastAPI) -> AsyncGenerator[None, None]:
        async with lifespan(app_instance, app_settings):
            yield

    instance = FastAPI(title="Dear Future Me API", lifespan=lifespan_wrapper)

    current_active_user = fastapi_users.current_user(active=True)

    if not app_settings.DEMO_MODE:
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

    chat_dependencies = []
    if not app_settings.SKIP_AUTH:
        chat_dependencies.append(Depends(current_active_user))
        print("INFO: SKIP_AUTH is false. Chat endpoints are protected.")
    else:
        print("INFO: SKIP_AUTH is true. Chat endpoints are NOT protected (authentication bypassed).")
    instance.include_router(chat_router, dependencies=chat_dependencies)

    instance.include_router(rag_router)

    @instance.get("/ping", tags=["health"])
    async def ping() -> dict[str, str]:
        return {"ping": "pong"}

    return instance


app = create_app()
