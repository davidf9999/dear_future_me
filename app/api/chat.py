import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.orchestrator import Orchestrator, get_orchestrator
from app.core.settings import get_settings

# Load configuration
cfg = get_settings()

# Limits from settings
_MAX_MSG = cfg.MAX_MESSAGE_LENGTH
_ASR_TIMEOUT = cfg.ASR_TIMEOUT_SECONDS

# Router without auth dependency
router = APIRouter(tags=["chat"])


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
    # The 'reply' variable from orchestrator.answer() is a dictionary like {"reply": "actual_message"}.
    # We need to extract the string value for the ChatResponse model.
    actual_reply_string = reply.get("reply", "Error: No reply content found.")
    return ChatResponse(reply=actual_reply_string)
