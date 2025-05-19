# /home/dfront/p/dir2ai_results/dear_future_me/app/safety_plan/schemas.py
# Full file content
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SafetyPlanBase(BaseModel):
    # Fields reverted to step_X names
    step_1_warning_signs: Optional[str] = Field(None, description="User-specific warning signs of escalating distress")
    step_2_internal_coping: Optional[str] = Field(None, description="User's internal coping strategies")
    step_3_social_distractions: Optional[str] = Field(None, description="Social contacts or settings for distraction")
    step_4_help_sources: Optional[str] = Field(
        None, description="People the user can reach out to for help (friends, family, therapist)"
    )
    step_5_professional_resources: Optional[str] = Field(
        None, description="Professional help resources (hotlines, clinics)"
    )
    step_6_environment_risk_reduction: Optional[str] = Field(
        None, description="Steps to make the immediate environment safer"
    )


class SafetyPlanCreate(SafetyPlanBase):
    pass


class SafetyPlanUpdate(SafetyPlanBase):
    pass


class SafetyPlanRead(SafetyPlanBase):
    user_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
