import pytest
from sqlalchemy import text

from app.auth.models import (  # Added SafetyPlanTable
    SafetyPlanTable,
    UserProfileTable,
    UserTable,
)
from app.db.session import get_async_session


@pytest.mark.asyncio
async def test_user_profile_table_exists():
    """Verify that the UserProfileTable was created by the test database setup."""
    async for session in get_async_session():
        result = await session.execute(text(f"SELECT 1 FROM {UserProfileTable.__tablename__} LIMIT 0"))
        assert result is not None, "Querying UserProfileTable failed, table might not exist."
        print(f"Successfully queried {UserProfileTable.__tablename__}, table exists.")
        break


@pytest.mark.asyncio
async def test_user_table_exists():
    """Verify that the UserTable exists."""
    async for session in get_async_session():
        result = await session.execute(text(f"SELECT 1 FROM {UserTable.__tablename__} LIMIT 0"))
        assert result is not None, "Querying UserTable failed, table might not exist."
        print(f"Successfully queried {UserTable.__tablename__}, table exists.")
        break


@pytest.mark.asyncio
async def test_safety_plan_table_exists():
    """Verify that the SafetyPlanTable was created by the test database setup."""
    async for session in get_async_session():
        result = await session.execute(text(f"SELECT 1 FROM {SafetyPlanTable.__tablename__} LIMIT 0"))
        assert result is not None, "Querying SafetyPlanTable failed, table might not exist."
        print(f"Successfully queried {SafetyPlanTable.__tablename__}, table exists.")
        break
