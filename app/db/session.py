# app/db/session.py
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG_SQL)

# expire_on_commit=False will prevent attributes from being expired
# after commit.
AsyncSessionMaker = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionMaker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_context() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope around a series of operations."""
    async with AsyncSessionMaker() as session:
        try:
            yield session
            # Note: We are not committing here by default.
            # The caller of this context manager is responsible for session.commit()
            # if changes made within the context need to be persisted.
            # For read-only operations, this is fine.
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
