# /home/dfront/code/dear_future_me/app/auth/models.py
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy.orm import relationship

# Crucial: Import the shared Base from app.db.session
from app.db.session import Base

# from sqlalchemy import Column, String # Uncomment if you have custom fields


print(f"DEBUG [app.auth.models]: id(Base) at import: {id(Base)}")


class UserTable(Base, SQLAlchemyBaseUserTableUUID):
    __tablename__ = "user"  # Explicitly define tablename

    # Relationship to UserProfileTable
    profile = relationship(
        "UserProfileTable",
        back_populates="user",
        uselist=False,  # One-to-one relationship
        cascade="all, delete-orphan",
    )
