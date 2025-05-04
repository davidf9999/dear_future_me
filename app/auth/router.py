# app/auth/router.py

import uuid
from fastapi import Depends
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import AuthenticationBackend, JWTStrategy
from fastapi_users.authentication.transport import BearerTransport
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.manager import BaseUserManager

from app.db.session import get_async_session  # AsyncSession dependency
from app.core.settings import get_settings, Settings

# Import your SQLAlchemy ORM table
from app.auth.models import UserTable  # ← ensure this file exists

# Import your Pydantic user schemas
from app.auth.schemas import (
    UserRead,  # inherits from schemas.BaseUser[UUID]
    UserCreate,  # inherits from schemas.BaseUserCreate
    UserUpdate,  # inherits from schemas.BaseUserUpdate
)


# 1) DB adapter dependency
async def get_user_db(session=Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, UserTable)


# 2) Custom user manager
class UserManager(BaseUserManager):
    reset_password_token_secret: str
    verification_token_secret: str

    def __init__(self, user_db):
        super().__init__(user_db)
        cfg = Settings()
        self.reset_password_token_secret = cfg.SECRET_KEY
        self.verification_token_secret = cfg.SECRET_KEY

    def parse_id(self, value: str) -> uuid.UUID:
        return uuid.UUID(value)


# 3) User manager dependency
async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


# 4) Auth transport
bearer_transport = BearerTransport(tokenUrl="/auth/login")


# 5) JWT strategy
def get_jwt_strategy(
    settings: Settings = Depends(get_settings),
) -> JWTStrategy:
    return JWTStrategy(
        secret=settings.SECRET_KEY,
        lifetime_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# 6) Authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# 7) FastAPI Users instance
fastapi_users = FastAPIUsers(
    get_user_manager,
    [auth_backend],
)

# 8) Routers
auth_router = fastapi_users.get_auth_router(auth_backend)
register_router = fastapi_users.get_register_router(UserRead, UserCreate)
register_router.routes[0].status_code = 201  # Set registration route to return 201
