# /home/dfront/code/dear_future_me/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Direct import of API routers from their specific modules
from app.api.chat import router as chat_router
from app.api.orchestrator import RagOrchestrator
from app.api.rag import router as rag_router
from app.api.user_profile import router as user_profile_router

# Import all necessary auth routers directly
from app.auth.router import (
    auth_router,
    register_router,
    reset_password_router,
    users_router,
    verify_router,
)
from app.core.settings import get_settings

# Load configuration
cfg = get_settings()


# Lifespan for application startup and shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize RagOrchestrator and store in app.state
    logging.info("Application startup: Initializing RagOrchestrator...")
    app.state.rag_orchestrator = RagOrchestrator()
    logging.info("RagOrchestrator initialized.")
    yield
    # Shutdown: Clean up resources if any
    logging.info("Application shutdown.")
    if hasattr(app.state, "rag_orchestrator"):
        del app.state.rag_orchestrator


app = FastAPI(lifespan=lifespan, title="Dear Future Me API")

# Include auth routers
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(reset_password_router, prefix="/auth/forgot-password", tags=["auth"])
app.include_router(verify_router, prefix="/auth/verify", tags=["auth"])
app.include_router(users_router, prefix="/users", tags=["users"])

# Include other API routers
app.include_router(chat_router, prefix="/chat", tags=["chat"])  # chat_router now has path "/text"
app.include_router(rag_router, prefix="/rag", tags=["rag"])
app.include_router(user_profile_router, prefix="/user_profile", tags=["user_profile"])


@app.get("/ping")
async def ping():
    """Sanity check."""
    return {"ping": "pong"}  # Corrected from "pong!" to "pong"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=cfg.DFM_API_HOST, port=cfg.DFM_API_PORT)
