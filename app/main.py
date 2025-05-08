# app/main.py

from fastapi import FastAPI, Depends
from app.core import settings
from app.db.init_db import init_db
from app.core.settings import get_settings

from app.auth.router import auth_router, register_router, fastapi_users
from app.auth.schemas import UserRead, UserUpdate

from app.api.chat import router as chat_router
from app.api.rag import router as rag_router, RagOrchestrator
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEMO_MODE:
        await init_db()
    app.state.rag_orchestrator = RagOrchestrator()
    yield
    # optional cleanup here


current_active_user = fastapi_users.current_user(active=True)

app = FastAPI(title="Dear Future Me API")

# Mount authentication endpoints
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# Users management
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Chat endpoints (conditionally protected based on demo mode)
if get_settings().DEMO_MODE:
    # In demo mode, chat endpoints are public
    app.include_router(chat_router)
else:
    # In normal mode, chat endpoints are protected
    app.include_router(
        chat_router,
        dependencies=[Depends(current_active_user)],
    )

# RAG ingestion and summarization endpoints
app.include_router(rag_router)


# Initialize DB tables and singleton RAG orchestrator on startup
@app.on_event("startup")
async def startup_event():
    await init_db()
    app.state.rag_orchestrator = RagOrchestrator()


# Health check
@app.get("/ping", tags=["health"])
async def ping():
    return {"ping": "pong"}
