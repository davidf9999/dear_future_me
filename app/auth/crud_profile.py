# app/auth/crud_profile.py
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .models import UserProfileTable
from .schemas import UserProfileCreate, UserProfileUpdate


async def get_user_profile(db: AsyncSession, user_id: UUID) -> Optional[UserProfileTable]:
    """
    Retrieve a user's profile by user_id.
    """
    result = await db.execute(select(UserProfileTable).where(UserProfileTable.user_id == user_id))
    return result.scalar_one_or_none()


async def create_user_profile(db: AsyncSession, user_id: UUID, profile_in: UserProfileCreate) -> UserProfileTable:
    """
    Create a new profile for a user.
    Assumes profile does not yet exist (checked in router).
    """
    db_profile = UserProfileTable(**profile_in.model_dump(exclude_unset=True), user_id=user_id)
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile


async def update_user_profile(
    db: AsyncSession, db_profile: UserProfileTable, profile_in: UserProfileUpdate
) -> UserProfileTable:
    """
    Update an existing user profile.
    """
    update_data = profile_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_profile, key, value)
    db.add(db_profile)
    await db.commit()
    await db.refresh(db_profile)
    return db_profile
