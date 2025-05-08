# app/db/session.py
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import get_settings

# ────────────────────────────────────────────────────────────────
#  Build ONE engine & sessionmaker when this module is imported
# ────────────────────────────────────────────────────────────────
_cfg = get_settings()

engine = create_async_engine(
    _cfg.DATABASE_URL,
    echo=_cfg.DEBUG_SQL,
    pool_pre_ping=True,  # keeps stale connections out
    pool_recycle=1_800,  # 30 min; avoids idle-timeout kicks
)

AsyncSessionMaker = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency – hands out a short-lived AsyncSession
    from the global connection-pool.
    """
    async with AsyncSessionMaker() as session:
        yield session
