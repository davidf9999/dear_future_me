# app/api/chat.py

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import asyncio

from app.core.settings import get_settings, Settings
from app.api.orchestrator import Orchestrator, get_orchestrator
from fastapi_users import FastAPIUsers
from app.auth.router import fastapi_users

_cfg: Settings = get_settings()
_MAX_MSG = _cfg.MAX_MESSAGE_LENGTH
_ASR_TIMEOUT = _cfg.ASR_TIMEOUT_SECONDS

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=_MAX_MSG)


class ChatResponse(BaseModel):
    reply: str


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
    try:
        reply = await asyncio.wait_for(
            orchestrator.answer(req.message), timeout=_ASR_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM orchestrator timed out",
        )
    return ChatResponse(reply=reply)
