# app/main.py
"""
FastAPI application entry-point.

Changes in this revision
────────────────────────
* Uses FastAPI lifespan instead of deprecated @app.on_event("startup").
* In DEMO_MODE → re-initialises the SQLite DB; otherwise leaves data intact.
* Verifies SECRET_KEY at startup.
* Disposes SQLAlchemy engine on shutdown for a graceful exit.
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy.exc import SQLAlchemyError

from app.api.chat import router as chat_router
from app.api.rag import RagOrchestrator
from app.api.rag import router as rag_router
from app.auth.router import auth_router, fastapi_users, register_router
from app.auth.schemas import UserRead, UserUpdate
from app.core.settings import get_settings
from app.db.init_db import init_db
from app.db.session import engine  # global engine defined once in app.db.session


# ────────────────────────────────────────────────────────────────
# Lifespan handler
# ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_settings()

    # Fatal mis-configuration guard ─────────────────────────────
    if not cfg.SECRET_KEY or cfg.SECRET_KEY.startswith("<fill"):
        raise RuntimeError(
            "❌ SECRET_KEY is not configured. Please set it in your .env "
            "before starting the server."
        )

    # Optional demo DB reset ────────────────────────────────────
    if cfg.DEMO_MODE:
        try:
            await init_db()
        except SQLAlchemyError as exc:
            raise RuntimeError(f"DB initialisation failed: {exc}") from exc

    # Singleton RAG orchestrator on app.state ───────────────────
    app.state.rag_orchestrator = RagOrchestrator()

    # Yield control to the app
    try:
        yield
    finally:
        # Graceful shutdown: close the SQLAlchemy connection-pool
        await engine.dispose()


# ────────────────────────────────────────────────────────────────
# FastAPI instance
# ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Dear Future Me API",
    lifespan=lifespan,
)

cfg = get_settings()
current_active_user = fastapi_users.current_user(active=True)

# ─── Auth routes ───────────────────────────────────────────────
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# ─── Chat routes: public in demo, protected otherwise ──────────
if cfg.DEMO_MODE:
    app.include_router(chat_router)
else:
    app.include_router(chat_router, dependencies=[Depends(current_active_user)])

# ─── RAG routes ────────────────────────────────────────────────
app.include_router(rag_router)


# ─── Healthcheck ───────────────────────────────────────────────
@app.get("/ping", tags=["health"])
async def ping():
    return {"ping": "pong"}
