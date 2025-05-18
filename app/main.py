# /home/dfront/code/dear_future_me/app/main.py
import logging
import os  # Added for os.makedirs
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.chat import router as chat_router
from app.api.rag import router as rag_router
from app.api.user_profile_router import router as user_profile_router
from app.auth.router import auth_router, register_router

# from app.auth.schemas import UserCreate, UserRead, UserUpdate # Not directly used here
from app.core.settings import Settings, get_settings
from app.db.migrate import upgrade_head
from app.db.session import (
    engine as global_engine,  # get_async_session is used by TestClient override
)
from app.safety_plan.router import router as safety_plan_router

# Initialize settings early if needed by other modules at import time
settings_instance = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    current_settings = get_settings()
    if current_settings.RUN_ALEMBIC_ON_STARTUP:
        logging.info("Running Alembic migrations on startup...")
        await upgrade_head()
        logging.info("Alembic migrations completed.")
    else:
        logging.info("Skipping Alembic migrations on startup (RUN_ALEMBIC_ON_STARTUP=False).")

    yield
    # Shutdown
    logging.info("Application shutdown: Disposing database engine...")
    await global_engine.dispose()
    logging.info("Database engine disposed.")


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Dear Future Me API",
        lifespan=lifespan,
    )

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    static_dir = os.path.join(project_root, "static")
    templates_dir = os.path.join(project_root, "templates")

    os.makedirs(static_dir, exist_ok=True)
    logging.info(f"Ensured static directory exists: {static_dir}")
    os.makedirs(templates_dir, exist_ok=True)
    logging.info(f"Ensured templates directory exists: {templates_dir}")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates = Jinja2Templates(directory=templates_dir)

    # Include routers
    app.include_router(auth_router, prefix="/auth", tags=["Auth"])
    app.include_router(register_router, prefix="/auth", tags=["Auth"])  # fastapi-users register router

    app.include_router(chat_router, prefix="/chat", tags=["Chat"])  # Ensure this is correct
    app.include_router(rag_router, prefix="/rag", tags=["RAG"])  # Ensure this is correct

    app.include_router(user_profile_router, prefix="/me/profile", tags=["User Profile"])
    app.include_router(safety_plan_router, prefix="/me/safety-plan", tags=["Safety Plan"])

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    async def root(request: Request):
        return templates.TemplateResponse("index.html", {"request": request})

    @app.get("/ping", tags=["Health"])
    async def ping():
        return {"ping": "pong"}

    return app


app = create_app()
