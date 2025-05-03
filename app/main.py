# app/main.py
from fastapi import FastAPI
from app.auth.router import auth_router, register_router

app = FastAPI(title="Dear Future Me API")

app.include_router(register_router, prefix="/auth", tags=["auth"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])

@app.get("/ping", tags=["health"])
async def ping():
    """Health check endpoint."""
    return {"ping": "pong"}
