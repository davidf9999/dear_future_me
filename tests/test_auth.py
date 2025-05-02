# tests/test_auth.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_register_and_login():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Register
        res = await ac.post(
            "/auth/register", json={"email": "a@b.com", "password": "secret"}
        )
        assert res.status_code == 201
        # Login
        res = await ac.post(
            "/auth/jwt/login", data={"username": "a@b.com", "password": "secret"}
        )
        assert "access_token" in res.json()
