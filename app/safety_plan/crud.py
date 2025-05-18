# /home/dfront/code/dear_future_me/app/safety_plan/crud.py
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import SafetyPlanTable
from app.safety_plan.schemas import SafetyPlanCreate, SafetyPlanUpdate


async def get_safety_plan_by_user_id(db: AsyncSession, user_id: UUID) -> Optional[SafetyPlanTable]:
    """
    Retrieves a safety plan for a given user_id.
    """
    result = await db.execute(select(SafetyPlanTable).filter(SafetyPlanTable.user_id == user_id))
    return result.scalars().first()


async def create_user_safety_plan(db: AsyncSession, user_id: UUID, plan_in: SafetyPlanCreate) -> SafetyPlanTable:
    """
    Creates a new safety plan for a user.
    Assumes checks for existing plan are done at the router level if only one plan per user is allowed.
    """
    db_plan = SafetyPlanTable(
        user_id=user_id,
        **plan_in.model_dump(exclude_unset=True),  # Use model_dump for Pydantic v2
    )
    db.add(db_plan)
    await db.commit()
    await db.refresh(db_plan)
    return db_plan


async def update_user_safety_plan(
    db: AsyncSession, user_id: UUID, plan_update_data: SafetyPlanUpdate
) -> Optional[SafetyPlanTable]:
    """
    Updates an existing safety plan for a user.
    Returns the updated plan object or None if not found.
    """
    db_plan = await get_safety_plan_by_user_id(db, user_id=user_id)
    if not db_plan:
        return None

    update_data = plan_update_data.model_dump(exclude_unset=True)  # Use model_dump for Pydantic v2

    if not update_data:  # No actual data provided for update
        return db_plan

    # Perform the update
    stmt = (
        update(SafetyPlanTable)
        .where(SafetyPlanTable.user_id == user_id)
        .values(**update_data)
        .returning(SafetyPlanTable)  # Ensure the ORM object is returned for refresh
    )
    result = await db.execute(stmt)
    await db.commit()

    # After commit, the result.scalars().first() might not be the ORM object
    # depending on dialect. It's safer to re-fetch or refresh the original db_plan.
    # However, for many dialects, .returning() works well with ORM.
    # For maximum safety and to get the ORM object with updated values:
    updated_plan_orm_object = result.scalar_one_or_none()
    if updated_plan_orm_object:
        # If the dialect supports returning the ORM object directly and it's instrumented
        return updated_plan_orm_object
    else:
        # Fallback to re-fetching if .returning didn't give us the ORM object
        # or if we want to be absolutely sure about the state after commit.
        await db.refresh(db_plan)  # Refresh the original instance
        return db_plan
