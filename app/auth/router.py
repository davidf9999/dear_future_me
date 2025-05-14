# /home/dfront/code/dear_future_me/app/auth/router.py
import uuid
from typing import Optional

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import UserTable  # Corrected import path for UserTable
from app.auth.schemas import UserCreate, UserRead, UserUpdate  # Import the schemas
from app.core.settings import get_settings
from app.db.session import get_async_session

cfg = get_settings()


class UserManager(UUIDIDMixin, BaseUserManager[UserTable, uuid.UUID]):
    reset_password_token_secret = cfg.SECRET_KEY
    verification_token_secret = cfg.SECRET_KEY

    async def on_after_register(self, user: UserTable, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Verification token: {token}")


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, UserTable)


async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)


bearer_transport = BearerTransport(tokenUrl="auth/login")


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=cfg.SECRET_KEY, lifetime_seconds=cfg.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserTable, uuid.UUID](get_user_manager, [auth_backend])

# This router can be included in your main FastAPI app
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(
    UserRead, UserCreate
)  # Use UserRead for response, UserCreate for request
reset_password_router = fastapi_users.get_reset_password_router()
verify_router = fastapi_users.get_verify_router(UserRead)
users_router = fastapi_users.get_users_router(UserRead, UserUpdate)

# You might want to combine these into a single router or include them selectively
# For simplicity, the example often shows including auth_router and register_router.
# If you need all functionalities, you'd include all relevant routers.
