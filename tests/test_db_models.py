# tests/test_db_models.py

import pytest
from sqlalchemy import text

from app.auth.models import UserProfileTable, UserTable
from app.db.session import get_async_session


@pytest.mark.asyncio
async def test_user_profile_table_exists():
    """Verify that the UserProfileTable was created by the test database setup."""
    async for session in get_async_session():
        # Attempt to select from the table. If it doesn't exist, this will raise an error.
        # We limit to 0 to avoid fetching data, just checking table existence.
        result = await session.execute(text(f"SELECT 1 FROM {UserProfileTable.__tablename__} LIMIT 0"))
        assert result is not None, "Querying UserProfileTable failed, table might not exist."
        # If the query executed without error, the table exists.
        print(f"Successfully queried {UserProfileTable.__tablename__}, table exists.")
        break  # Exit the async generator after the first session


@pytest.mark.asyncio
async def test_user_table_exists():
    """Verify that the UserTable exists (should be true if auth tests pass, but good to check)."""
    async for session in get_async_session():
        result = await session.execute(text(f"SELECT 1 FROM {UserTable.__tablename__} LIMIT 0"))
        assert result is not None, "Querying UserTable failed, table might not exist."
        print(f"Successfully queried {UserTable.__tablename__}, table exists.")
        break  # Exit the async generator after the first session
