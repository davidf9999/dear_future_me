from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import asyncio

from app.core.settings import get_settings
from app.api.orchestrator import get_orchestrator, Orchestrator
from fastapi_users import FastAPIUsers
from app.auth.router import fastapi_users

# Load configuration
cfg = get_settings()

# Limits from settings
_MAX_MSG = cfg.MAX_MESSAGE_LENGTH
_ASR_TIMEOUT = cfg.ASR_TIMEOUT_SECONDS

# Dependency for auth
current_active_user = fastapi_users.current_user(active=True)

# In demo mode, skip auth; otherwise require active user
router = APIRouter(
    tags=["chat"],
    dependencies=[] if cfg.DEMO_MODE else [Depends(current_active_user)],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MSG)


class ChatResponse(BaseModel):
    reply: str


@router.post(
    "/chat/text",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat_text(
    req: ChatRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    """
    Accepts a user message, routes through the Orchestrator (crisis vs RAG),
    and returns a single reply.
    """
    try:
        reply = await asyncio.wait_for(
            orchestrator.answer(req.message),
            timeout=_ASR_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM orchestrator timed out",
        )
    return ChatResponse(reply=reply)
