# app/main.py

from fastapi import FastAPI, Depends
from app.db.init_db import init_db

from app.auth.router import auth_router, register_router, fastapi_users
from app.auth.schemas import UserRead, UserUpdate

from app.api.chat import router as chat_router, current_active_user, get_orchestrator
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
