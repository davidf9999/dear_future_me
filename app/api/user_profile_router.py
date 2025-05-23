# app/api/user_profile_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import crud_profile  # Corrected import path
from app.auth.models import UserTable
from app.auth.router import fastapi_users  # To get current_active_user
from app.auth.schemas import (  # Corrected import path
    UserProfileCreate,
    UserProfileRead,
    UserProfileUpdate,
)
from app.db.session import get_async_session

router = APIRouter()

current_active_user = fastapi_users.current_user(active=True)


@router.post(
    "",  # Path relative to the prefix in main.py (e.g., /me/profile)
    response_model=UserProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Profile",
    description="Create a new profile for the authenticated user. Users can only have one profile.",
)
async def create_profile(
    profile_in: UserProfileCreate,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    existing_profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if existing_profile:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Profile already exists for this user.",
        )
    created_profile = await crud_profile.create_user_profile(db=db, user_id=user.id, profile_in=profile_in)
    return created_profile


@router.get(
    "",  # Path relative to the prefix in main.py (e.g., /me/profile)
    response_model=UserProfileRead,
    summary="Get User Profile",
    description="Retrieve the profile for the authenticated user.",
)
async def get_profile(
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found for this user.",
        )
    return profile


@router.put(
    "",  # Path relative to the prefix in main.py (e.g., /me/profile)
    response_model=UserProfileRead,
    summary="Update User Profile",
    description="Update the profile for the authenticated user.",
)
async def update_profile(
    profile_in: UserProfileUpdate,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    db_profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if not db_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found, cannot update.",
        )
    updated_profile = await crud_profile.update_user_profile(db=db, db_profile=db_profile, profile_in=profile_in)
    return updated_profile
