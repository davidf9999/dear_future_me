# app/auth/router.py
import uuid
from typing import (
    Optional,  # Added for Request type hint if you uncomment on_after_register
)

from fastapi import (  # Added Request for on_after_register if uncommented
    Depends,
    Request,
)
from fastapi_users import FastAPIUsers, UUIDIDMixin  # Added UUIDIDMixin
from fastapi_users.authentication import AuthenticationBackend, JWTStrategy
from fastapi_users.authentication.transport import BearerTransport
from fastapi_users.db import SQLAlchemyUserDatabase

# SQLAlchemyBaseUserTableUUID is not directly used here but UserTable inherits from it.
# from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from fastapi_users.manager import BaseUserManager

from app.auth.models import UserTable
from app.auth.schemas import UserCreate, UserRead  # Added UserUpdate
from app.core.settings import get_settings
from app.db.session import get_async_session


# ────────────────────────────  DB adapter  ──────────────────────────────
async def get_user_db(session=Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, UserTable)


# ───────────────────────────  User manager  ─────────────────────────────
class UserManager(UUIDIDMixin, BaseUserManager[UserTable, uuid.UUID]):  # Ensure it matches UserTable and UUID
    cfg = get_settings()  # single lookup

    reset_password_token_secret: str = cfg.SECRET_KEY
    verification_token_secret: str = cfg.SECRET_KEY

    # Optional: Add lifecycle hooks if needed
    async def on_after_register(self, user: UserTable, request: Optional[Request] = None):
        print(f"User {user.id} has registered.")

    async def on_after_forgot_password(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"User {user.id} has forgot their password. Reset token: {token}")

    async def on_after_request_verify(self, user: UserTable, token: str, request: Optional[Request] = None):
        print(f"Verification requested for user {user.id}. Verification token: {token}")

    # fastapi-users BaseUserManager expects parse_id if your user ID isn't int.
    # Since UserTable uses SQLAlchemyBaseUserTableUUID, this is handled by UUIDIDMixin.
    # However, if you were not using UUIDIDMixin and had a custom UUID handling,
    # you might need something like this:
    # def parse_id(self, value: str) -> uuid.UUID:
    #     return uuid.UUID(value)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# ──────────────────────────  Auth components  ───────────────────────────
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")  # Corrected tokenUrl to match fastapi-users default


def get_jwt_strategy() -> JWTStrategy:
    cfg = get_settings()
    return JWTStrategy(
        secret=cfg.SECRET_KEY,
        lifetime_seconds=cfg.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[UserTable, uuid.UUID](get_user_manager, [auth_backend])

auth_router = fastapi_users.get_auth_router(auth_backend)
# Ensure UserRead and UserCreate are correctly imported and used
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
# The following line to change status code is fine if you need it.
register_router.routes[0].status_code = 201  # type: ignore[attr-defined]

# Add these current_user dependencies, similar to what's in users.py
current_active_user = fastapi_users.current_user(active=True)
current_active_verified_user = fastapi_users.current_user(active=True, verified=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
