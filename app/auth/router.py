# app/auth/router.py

import uuid

from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, JWTStrategy
from fastapi_users.authentication.transport import BearerTransport
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.manager import BaseUserManager

from app.auth.models import UserTable
from app.auth.schemas import UserCreate, UserRead
from app.core.settings import get_settings
from app.db.session import get_async_session


# ────────────────────────────  DB adapter  ──────────────────────────────
async def get_user_db(session=Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, UserTable)


# ───────────────────────────  User manager  ─────────────────────────────
class UserManager(BaseUserManager):
    cfg = get_settings()  # single lookup

    reset_password_token_secret: str = cfg.SECRET_KEY
    verification_token_secret: str = cfg.SECRET_KEY

    def parse_id(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)


async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# ──────────────────────────  Auth components  ───────────────────────────
bearer_transport = BearerTransport(tokenUrl="/auth/login")


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

fastapi_users = FastAPIUsers(get_user_manager, [auth_backend])

auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
register_router.routes[0].status_code = 201
