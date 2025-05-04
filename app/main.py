# app/main.py

from fastapi import FastAPI, Depends
from app.auth.router import auth_router, register_router, fastapi_users
from app.auth.schemas import UserRead, UserUpdate
from app.api.chat import (
    router as chat_router,
    current_active_user,
    get_orchestrator as get_chat_orchestrator,
)
from app.api.rag import router as rag_router, get_rag_orchestrator, RagOrchestrator

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

# Chat endpoints (protected)
app.include_router(
    chat_router,
    prefix="",
    tags=["chat"],
    dependencies=[Depends(current_active_user)],
)

# RAG ingestion and summarization endpoints
app.include_router(
    rag_router,
    prefix="",
    tags=["rag"],
)


# Initialize singleton RAG orchestrator on startup
@app.on_event("startup")
async def startup_event():
    # Create a single RagOrchestrator instance and store in app state
    app.state.rag_orchestrator = RagOrchestrator()


# Health check
@app.get("/ping", tags=["health"])
async def ping():
    """Health check endpoint."""
    return {"ping": "pong"}
