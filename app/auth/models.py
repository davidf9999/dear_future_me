# app/auth/models.py

import uuid
from sqlalchemy import Column, String, Boolean
from sqlalchemy.orm import DeclarativeBase
from fastapi_users.db import SQLAlchemyBaseUserTableUUID


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserTable(SQLAlchemyBaseUserTableUUID, Base):
    """
    The users table for FastAPI Users.

    Inherits:
      - id (UUID primary key)
      - email (str, unique)
      - hashed_password (str)
      - is_active (bool)
      - is_superuser (bool)
      - is_verified (bool)

    You can add extra columns below:
    """

    # Optional profile fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)

    # (The inherited booleans cover active/superuser/verified status.)
