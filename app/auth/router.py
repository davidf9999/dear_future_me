# app/auth/router.py

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy
from fastapi_users.db import SQLAlchemyUserDatabase

from app.db.session import get_async_session  # AsyncSession dependency
from app.core.settings import settings  # Pydantic BaseSettings

# Import your SQLAlchemy ORM table
from app.auth.models import UserTable  # ← ensure this file exists

# Import your Pydantic user schemas
from app.auth.schemas import (
    UserRead,  # inherits from schemas.BaseUser[UUID]
    UserCreate,  # inherits from schemas.BaseUserCreate
    UserUpdate,  # inherits from schemas.BaseUserUpdate
    UserDB,  # inherits from schemas.BaseUserDB[UUID]
)


# 1) Dependency that yields the user database adapter
async def get_user_db(session=Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(UserTable, session)


# 2) Define your JWT strategy
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# 3) Instantiate FastAPIUsers with the four schema types
fastapi_users = FastAPIUsers[UserRead, UserCreate, UserUpdate, UserDB](
    get_user_db,  # user_db dependency
    [get_jwt_strategy()],  # list of auth backends
    UserRead,  # Pydantic model for reading
    UserCreate,  # Pydantic model for creating
    UserUpdate,  # Pydantic model for updating
    UserDB,  # Pydantic model stored in DB
)  # see “Define your schemas” for details :contentReference[oaicite:0]{index=0}

# 4) Export routers for registration and authentication
auth_router = fastapi_users.get_auth_router(get_jwt_strategy())
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
