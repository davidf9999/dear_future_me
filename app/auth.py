# app/auth.py
from fastapi_users import FastAPIUsers, models as _fu_models
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi_users.authentication import JWTStrategy
from app.auth.models import UserTable
from app.db.session import AsyncSessionLocal

SECRET = settings.SECRET_KEY


def get_user_db():
    yield SQLAlchemyUserDatabase(UserTable, AsyncSessionLocal())


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


fastapi_users = FastAPIUsers(
    get_user_manager=get_user_db,
    auth_backends=[get_jwt_strategy()],
    user_model=_fu_models.BaseUser,
    user_create_model=_fu_models.BaseUserCreate,
    user_update_model=_fu_models.BaseUserUpdate,
    user_db_model=_fu_models.BaseUserDB,
)

auth_router = fastapi_users.get_auth_router(get_jwt_strategy())
register_router = fastapi_users.get_register_router()
