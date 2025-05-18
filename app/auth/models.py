# app/auth/models.py
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import TIMESTAMP, UUID, Column, Date, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func  # For server-side timestamp defaults


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserTable(SQLAlchemyBaseUserTableUUID, Base):
    """User table (inherits core FastAPI-Users columns)."""

    __tablename__ = "UserTable"  # Explicitly set table name

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)


class UserProfileTable(Base):
    """Stores core user attributes and preferences."""

    __tablename__ = "UserProfileTable"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("UserTable.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name = Column(String(255), nullable=True)
    future_me_persona_summary = Column(Text, nullable=True)

    # Therapeutic and Tone Alignment
    gender_identity_pronouns = Column(String(100), nullable=True)
    therapeutic_setting = Column(String(255), nullable=True)
    therapy_start_date = Column(Date, nullable=True)
    dfm_use_integration_status = Column(String(50), nullable=True)
    primary_emotional_themes = Column(Text, nullable=True)
    recent_triggers_events = Column(Text, nullable=True)
    emotion_regulation_strengths = Column(Text, nullable=True)
    identified_values = Column(Text, nullable=True)
    self_reported_goals = Column(Text, nullable=True)
    therapist_language_to_mirror = Column(Text, nullable=True)
    user_emotional_tone_preference = Column(String(100), nullable=True)
    tone_alignment = Column(String(100), nullable=True)

    # created_at and updated_at for UserProfileTable (as per data_structure.md)
    # Note: The trigger logic from data_structure.md for updated_at
    # would typically be handled in a database-specific migration or via SQLAlchemy events.
    # For now, we'll define the columns.
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SafetyPlanTable(Base):
    """Stores the user's structured safety plan."""

    __tablename__ = "SafetyPlanTable"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("UserTable.id", ondelete="CASCADE"),
        primary_key=True,
    )
    step_1_warning_signs = Column(Text, nullable=True)
    step_2_internal_coping = Column(Text, nullable=True)
    step_3_social_distractions = Column(Text, nullable=True)
    step_4_help_sources = Column(Text, nullable=True)
    step_5_professional_resources = Column(Text, nullable=True)
    step_6_environment_risk_reduction = Column(Text, nullable=True)

    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
