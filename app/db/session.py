# app/db/session.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from fastapi import Depends

from app.core.settings import get_settings, Settings

async def get_async_session(
    settings: Settings = Depends(get_settings),
) -> AsyncGenerator[AsyncSession, None]:
    """
    On each request, create a new engine/session using the
    latest settings.DATABASE_URL.
    """
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncSessionLocal() as session:
        yield session
