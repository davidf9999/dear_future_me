# Full file content
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import TIMESTAMP  # Added Integer
from sqlalchemy import Date  # Added Date
from sqlalchemy import UUID as SQLAlchemyUUID  # Import SQLAlchemy's UUID type
from sqlalchemy import Column, ForeignKey, Integer, Text  # Added Integer
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserTable(SQLAlchemyBaseUserTableUUID, Base):
    """User table (inherits core FastAPI-Users columns)."""

    __tablename__ = "UserTable"

    # id is inherited from SQLAlchemyBaseUserTableUUID and is already a UUID type
    first_name = Column(Text, nullable=True)
    last_name = Column(Text, nullable=True)


class UserProfileTable(Base):
    """Stores core user attributes and preferences."""

    __tablename__ = "UserProfileTable"

    user_id = Column(
        SQLAlchemyUUID(as_uuid=True),  # Use SQLAlchemy's UUID type here
        ForeignKey("UserTable.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name = Column(Text, nullable=True)
    future_me_persona_summary = Column(Text, nullable=True)
    therapeutic_setting = Column(Text, nullable=True)
    gender_identity_pronouns = Column(Text, nullable=True)
    emotion_regulation_strengths = Column(Text, nullable=True)
    # Add other fields that were previously missing or defined in later migrations
    therapy_start_date = Column(Date, nullable=True)
    dfm_use_integration_status = Column(Text, nullable=True)
    primary_emotional_themes = Column(Text, nullable=True)
    recent_triggers_events = Column(Text, nullable=True)
    identified_values = Column(Text, nullable=True)
    self_reported_goals = Column(Text, nullable=True)
    therapist_language_to_mirror = Column(Text, nullable=True)
    user_emotional_tone_preference = Column(Text, nullable=True)
    tone_alignment = Column(Text, nullable=True)

    # New fields requested
    c_ssrs_status = Column(Text, nullable=True)
    bdi_ii_score = Column(Integer, nullable=True)
    inq_status = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SafetyPlanTable(Base):
    """Stores the user's structured safety plan."""

    __tablename__ = "SafetyPlanTable"

    user_id = Column(
        SQLAlchemyUUID(as_uuid=True),  # Use SQLAlchemy's UUID type here
        ForeignKey("UserTable.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Actual safety plan fields - Reverted to step_X names
    step_1_warning_signs = Column(Text, nullable=True)
    step_2_internal_coping = Column(Text, nullable=True)
    step_3_social_distractions = Column(Text, nullable=True)
    step_4_help_sources = Column(Text, nullable=True)
    step_5_professional_resources = Column(Text, nullable=True)
    step_6_environment_risk_reduction = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
