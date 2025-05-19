# app/auth/schemas.py
import datetime
import uuid
from typing import Optional

from fastapi_users import schemas
from pydantic import UUID4, BaseModel, Field


# Table: User
class UserRead(schemas.BaseUser[uuid.UUID]):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserCreate(schemas.BaseUserCreate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


class UserUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None


# Table: UserProfile


class UserProfileBase(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    future_me_persona_summary: Optional[str] = None
    gender_identity_pronouns: Optional[str] = Field(None, max_length=100)
    therapeutic_setting: Optional[str] = Field(None, max_length=255)
    therapy_start_date: Optional[datetime.date] = None
    dfm_use_integration_status: Optional[str] = Field(None, max_length=50)
    primary_emotional_themes: Optional[str] = None
    recent_triggers_events: Optional[str] = None
    emotion_regulation_strengths: Optional[str] = None
    identified_values: Optional[str] = None
    self_reported_goals: Optional[str] = None
    therapist_language_to_mirror: Optional[str] = None
    user_emotional_tone_preference: Optional[str] = Field(None, max_length=100)
    tone_alignment: Optional[str] = Field(None, max_length=100)

    # New fields
    c_ssrs_status: Optional[str] = Field(
        None,
        description="Latest C-SSRS status (e.g., 'Moderate ideation, no plan'). Used for adapting grounding questions.",
    )
    bdi_ii_score: Optional[int] = Field(
        None, description="Latest BDI-II score. Used to inform prompts regarding hopelessness or cognitive distortions."
    )
    inq_status: Optional[str] = Field(
        None,
        description="Latest INQ status (e.g., 'High perceived burdensomeness, low belongingness'). Used to emphasize connectedness.",
    )


class UserProfileCreate(UserProfileBase):
    pass


class UserProfileUpdate(UserProfileBase):  # For PUT/PATCH later
    pass


class UserProfileRead(UserProfileBase):
    user_id: UUID4
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True  # For Pydantic v2 (orm_mode for v1)
