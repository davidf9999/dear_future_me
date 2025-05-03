# app/db/init_db.py
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.auth.models import Base
from app.core.settings import Settings


async def init_db():
    """Drop and recreate all tables using the DATABASE_URL
    from a fresh Settings() instance.
    """
    cfg = Settings()
    engine = create_async_engine(cfg.DATABASE_URL, echo=True)    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())