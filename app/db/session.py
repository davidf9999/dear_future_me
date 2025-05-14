# /home/dfront/code/dear_future_me/app/db/session.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.settings import get_settings

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL

# This is the single, authoritative Base for all SQLAlchemy models in the application.
Base = declarative_base()
print(f"DEBUG [app.db.session]: id(Base) at definition: {id(Base)}")

# This engine is for the main application. Tests will use a separate engine.
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
