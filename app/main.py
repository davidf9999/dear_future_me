# app/main.py
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.chat import router as chat_router
from app.api.rag import RagOrchestrator
from app.api.rag import router as rag_router
from app.auth.router import auth_router, fastapi_users, register_router
from app.auth.schemas import UserRead, UserUpdate
from app.core.settings import get_settings
from app.db.init_db import init_db  # demo-mode reset
from app.db.migrate import upgrade_head  # ← NEW: programmatic Alembic
from app.db.session import engine  # for graceful shutdown

cfg = get_settings()
current_active_user = fastapi_users.current_user(active=True)


# ────────────────────────────────────────────────────────────────
# Lifespan
# ────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    if cfg.DEMO_MODE:
        # Drop & recreate tables for every demo run
        await init_db()
    else:
        # Apply any outstanding Alembic migrations *once*
        try:
            upgrade_head()  # blocks <100 ms if already at head
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Alembic upgrade failed: {exc}") from exc

    # Shared singleton objects
    app.state.rag_orchestrator = RagOrchestrator()

    yield

    # Graceful shutdown
    await engine.dispose()


# ────────────────────────────────────────────────────────────────
# FastAPI app
# ────────────────────────────────────────────────────────────────
app = FastAPI(title="Dear Future Me API", lifespan=lifespan)

# Auth endpoints
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Chat endpoints (public in demo, protected in prod)
if cfg.DEMO_MODE:
    app.include_router(chat_router)
else:
    app.include_router(chat_router, dependencies=[Depends(current_active_user)])

# RAG endpoints
app.include_router(rag_router)


# Health check
@app.get("/ping", tags=["health"])
async def ping() -> dict[str, str]:
    return {"ping": "pong"}
