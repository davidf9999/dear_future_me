# app/api/user_profile.py
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import (
    UserTable,  # This import should now point to the definitive UserTable
)
from app.auth.router import fastapi_users
from app.crud.user_profile import (
    create_user_profile,
    get_user_profile,
    update_user_profile,
)
from app.db.session import get_async_session

router = APIRouter(tags=["user_profile"])

# Dependency to get the current authenticated user
current_active_user = fastapi_users.current_user(active=True)


# Pydantic model for User Profile data (for request/response bodies)
class UserProfileBase(BaseModel):
    name: Optional[str] = None
    future_me_persona_summary: Optional[str] = None
    key_therapeutic_language: Optional[str] = None
    core_values_summary: Optional[str] = None
    safety_plan_summary: Optional[str] = None

    class Config:
        from_attributes = True


# Response model (can inherit from base if no extra fields needed)
class UserProfileResponse(UserProfileBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


@router.get("/me", response_model=UserProfileResponse)
async def read_user_profile_me(
    user: UserTable = Depends(current_active_user), db: AsyncSession = Depends(get_async_session)
):
    """Get the profile for the currently authenticated user."""
    user_profile = await get_user_profile(db, user_id=user.id)
    if user_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")
    return user_profile


@router.post("/", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user_profile_for_me(
    profile_data: UserProfileBase,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Create a user profile for the currently authenticated user."""
    existing_profile = await get_user_profile(db, user_id=user.id)
    if existing_profile:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User profile already exists")

    profile_dict = profile_data.model_dump(exclude_unset=True)

    user_profile = await create_user_profile(db, user_id=user.id, profile_data=profile_dict)
    return user_profile


@router.put("/me", response_model=UserProfileResponse)
async def update_user_profile_me(
    profile_data: UserProfileBase,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Update the profile for the currently authenticated user."""
    user_profile = await get_user_profile(db, user_id=user.id)
    if user_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found")

    profile_dict = profile_data.model_dump(exclude_unset=True)

    updated_profile = await update_user_profile(db, user_profile, profile_dict)
    return updated_profile
