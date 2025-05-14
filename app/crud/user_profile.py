# app/crud/user_profile.py
import uuid
from typing import Any, Dict, Optional  # Import Dict and Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import UserProfileTable


async def get_user_profile(db_session: AsyncSession, user_id: uuid.UUID) -> Optional[UserProfileTable]:
    """Retrieves a user profile by user ID."""
    result = await db_session.execute(select(UserProfileTable).filter(UserProfileTable.user_id == user_id))
    return result.scalars().first()


async def create_user_profile(
    db_session: AsyncSession, user_id: uuid.UUID, profile_data: Dict[str, Any]
) -> UserProfileTable:
    """Creates a new user profile."""
    # Ensure user_id is in the profile_data for instantiation
    profile_data["user_id"] = user_id
    user_profile = UserProfileTable(**profile_data)
    db_session.add(user_profile)
    await db_session.commit()
    await db_session.refresh(user_profile)
    return user_profile


async def update_user_profile(
    db_session: AsyncSession, user_profile: UserProfileTable, profile_data: Dict[str, Any]
) -> UserProfileTable:
    """Updates an existing user profile."""
    for field, value in profile_data.items():
        # Only update fields that are part of the model and are provided
        if hasattr(user_profile, field) and value is not None:
            setattr(user_profile, field, value)

    # SQLAlchemy's onupdate handles updated_at
    await db_session.commit()
    await db_session.refresh(user_profile)
    return user_profile
