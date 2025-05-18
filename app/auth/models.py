# /home/dfront/code/dear_future_me/app/auth/models.py

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import TIMESTAMP
from sqlalchemy import UUID as SQLAlchemyUUID  # Import SQLAlchemy's UUID type
from sqlalchemy import Column, ForeignKey, Text
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
    # Actual safety plan fields
    warning_signs = Column(Text, nullable=True)
    coping_strategies = Column(Text, nullable=True)
    emergency_contacts = Column(Text, nullable=True)  # Could be JSON string
    professional_help_contacts = Column(Text, nullable=True)  # Could be JSON string
    safe_environment_notes = Column(Text, nullable=True)
    reasons_for_living = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
