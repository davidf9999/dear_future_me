# /home/dfront/code/dear_future_me/app/auth/routers/profile_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import crud_profile
from app.auth import schemas as auth_schemas
from app.auth.models import (
    UserTable as UserModel,  # Renamed to avoid confusion with User schema
)

# Import current_active_user from app.auth.router where it's now defined
from app.auth.router import current_active_user
from app.db.session import get_async_session

router = APIRouter()


@router.post(
    "/me/profile",
    response_model=auth_schemas.UserProfileRead,
    status_code=201,
    summary="Create User Profile for Current User",
    tags=["User Profile"],
)
async def create_my_user_profile(
    profile_in: auth_schemas.UserProfileCreate,
    db: AsyncSession = Depends(get_async_session),
    user: UserModel = Depends(current_active_user),
):
    """
    Create a profile for the currently authenticated user.
    Returns a 409 conflict error if a profile already exists.
    """
    existing_profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if existing_profile:
        raise HTTPException(status_code=409, detail="Profile already exists for this user.")

    profile = await crud_profile.create_user_profile(db, user_id=user.id, profile_in=profile_in)
    return profile


@router.get(
    "/me/profile",
    response_model=auth_schemas.UserProfileRead,
    summary="Get User Profile for Current User",
    tags=["User Profile"],
)
async def read_my_user_profile(
    db: AsyncSession = Depends(get_async_session),
    user: UserModel = Depends(current_active_user),
):
    """
    Retrieve the profile for the currently authenticated user.
    Returns a 404 error if no profile is found.
    """
    profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found for this user.")
    return profile


@router.put(
    "/me/profile",
    response_model=auth_schemas.UserProfileRead,
    summary="Update User Profile for Current User",
    tags=["User Profile"],
)
async def update_my_user_profile(
    profile_in: auth_schemas.UserProfileUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: UserModel = Depends(current_active_user),
):
    """
    Update the profile for the currently authenticated user.
    Creates a profile if one does not exist (upsert behavior).
    """
    db_profile = await crud_profile.get_user_profile(db, user_id=user.id)
    if db_profile is None:
        profile_create_data = auth_schemas.UserProfileCreate(**profile_in.model_dump(exclude_unset=True))
        return await crud_profile.create_user_profile(db, user_id=user.id, profile_in=profile_create_data)

    updated_profile = await crud_profile.update_user_profile(db, db_profile=db_profile, profile_in=profile_in)
    return updated_profile
