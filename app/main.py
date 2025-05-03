# app/main.py

from fastapi import FastAPI
from app.auth.router import auth_router, register_router, fastapi_users
from app.auth.schemas import UserRead, UserUpdate

app = FastAPI(title="Dear Future Me API")

# Existing auth endpoints
app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])

# ✅ Correct way to mount the users router
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

@app.get("/ping", tags=["health"])
async def ping():
    """Health check endpoint."""
    return {"ping": "pong"}
