# app/db/init_db.py
import asyncio

from sqlalchemy.ext.asyncio import create_async_engine

from app.auth.models import Base
from app.core.settings import Settings


async def init_db():
    """
    Drops all tables using the DATABASE_URL from a fresh Settings() instance.
    Table creation will be handled by Alembic migrations.
    """
    cfg = Settings()  # Ensure settings are loaded if DATABASE_URL comes from env
    engine = create_async_engine(cfg.DATABASE_URL, echo=cfg.DEBUG_SQL)  # Use DEBUG_SQL from settings
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        # await conn.run_sync(Base.metadata.create_all) # REMOVE THIS LINE
    print("INFO (init_db): All tables dropped.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(init_db())
