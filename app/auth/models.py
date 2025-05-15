# app/auth/models.py
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import UUID, Column, Date, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase


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
    dfm_use_integration_status = Column(String(50), nullable=True)  # TODO: Add CHECK constraint
    primary_emotional_themes = Column(Text, nullable=True)
    recent_triggers_events = Column(Text, nullable=True)
    emotion_regulation_strengths = Column(Text, nullable=True)
    identified_values = Column(Text, nullable=True)
    self_reported_goals = Column(Text, nullable=True)
    therapist_language_to_mirror = Column(Text, nullable=True)
    user_emotional_tone_preference = Column(String(100), nullable=True)
    tone_alignment = Column(String(100), nullable=True)

    # Optional fields for clinical questionnaire summaries (TODO: Add these fields)


# Note: The SQL CREATE TABLE statements with triggers shown in data_structure.md
# are typically for database-level definitions or documentation.
# In SQLAlchemy, you define the Python models, and Alembic generates the SQL
# for CREATE TABLE, ALTER TABLE, etc. Triggers might need manual definition
# in migration scripts or using SQLAlchemy's DDL event listeners if needed.
# For this step, defining the model is sufficient.
