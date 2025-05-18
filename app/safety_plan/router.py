# /home/dfront/code/dear_future_me/app/safety_plan/router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserTable
from app.auth.router import fastapi_users  # To get current_active_user
from app.db.session import get_async_session
from app.safety_plan import crud
from app.safety_plan.schemas import SafetyPlanCreate, SafetyPlanRead, SafetyPlanUpdate

router = APIRouter()

current_active_user = fastapi_users.current_user(active=True)


@router.post(
    "/me/safety-plan",
    response_model=SafetyPlanRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Safety Plan",
    description="Create a new safety plan for the authenticated user. Users can only have one safety plan.",
)
async def create_safety_plan(
    plan_in: SafetyPlanCreate,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    existing_plan = await crud.get_safety_plan_by_user_id(db, user_id=user.id)
    if existing_plan:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Safety plan already exists for this user.",
        )
    created_plan = await crud.create_user_safety_plan(db=db, user_id=user.id, plan_in=plan_in)
    return created_plan


@router.get(
    "/me/safety-plan",
    response_model=SafetyPlanRead,
    summary="Get Safety Plan",
    description="Retrieve the safety plan for the authenticated user.",
)
async def get_safety_plan(
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    plan = await crud.get_safety_plan_by_user_id(db, user_id=user.id)
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety plan not found for this user.",
        )
    return plan


@router.put(
    "/me/safety-plan",
    response_model=SafetyPlanRead,
    summary="Update Safety Plan",
    description="Update the safety plan for the authenticated user.",
)
async def update_safety_plan(
    plan_update_data: SafetyPlanUpdate,
    user: UserTable = Depends(current_active_user),
    db: AsyncSession = Depends(get_async_session),
):
    updated_plan = await crud.update_user_safety_plan(db=db, user_id=user.id, plan_update_data=plan_update_data)
    if not updated_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety plan not found for this user, cannot update.",
        )
    return updated_plan
