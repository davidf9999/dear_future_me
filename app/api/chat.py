# app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import asyncio

from app.core.settings import settings
from app.api.orchestrator import Orchestrator, get_orchestrator
from fastapi_users import FastAPIUsers
from app.auth.router import fastapi_users

router = APIRouter(tags=["chat"])


# Pydantic model for text chat request
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=settings.MAX_MESSAGE_LENGTH)


# Pydantic model for text chat response
class ChatResponse(BaseModel):
    reply: str


# Dependency to enforce auth
current_active_user = fastapi_users.current_user(active=True)


@router.post(
    "/chat/text",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(current_active_user)],
)
async def chat_text(
    req: ChatRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
):
    # Enforce a timeout for the orchestrator call
    try:
        reply = await asyncio.wait_for(
            orchestrator.answer(req.message), timeout=settings.ASR_TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM orchestrator timed out",
        )
    return ChatResponse(reply=reply)
