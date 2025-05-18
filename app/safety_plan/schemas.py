# /home/dfront/code/dear_future_me/app/safety_plan/schemas.py
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SafetyPlanBase(BaseModel):
    warning_signs: Optional[str] = Field(None, description="Personal warning signs.")
    coping_strategies: Optional[str] = Field(None, description="Effective coping strategies.")
    emergency_contacts: Optional[str] = Field(
        None, description="Emergency contacts (e.g., JSON string or structured text)."
    )
    professional_help_contacts: Optional[str] = Field(None, description="Contacts for professional help.")
    safe_environment_notes: Optional[str] = Field(None, description="Notes on making the environment safe.")
    reasons_for_living: Optional[str] = Field(None, description="Personal reasons for living.")
    # For more complex fields like lists of strategies or contacts,
    # you might use List[str] or even nested Pydantic models in the future.
    # For now, simple text fields are a good start.


class SafetyPlanCreate(SafetyPlanBase):
    # All fields from SafetyPlanBase are optional for creation,
    # allowing a user to build their plan incrementally.
    # If some fields were mandatory on creation, they would be listed here without Optional.
    pass


class SafetyPlanUpdate(SafetyPlanBase):
    # All fields are optional for update.
    pass


class SafetyPlanRead(SafetyPlanBase):
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Replaces orm_mode = True in Pydantic v2
