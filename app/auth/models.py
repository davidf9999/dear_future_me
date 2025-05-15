# app/auth/models.py
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import Column, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class UserTable(SQLAlchemyBaseUserTableUUID, Base):
    """User table (inherits core FastAPI-Users columns)."""

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
