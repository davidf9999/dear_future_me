# tests/test_main.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_ping():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        res = await ac.get("/ping")
    assert res.status_code == 200
    assert res.json() == {"ping": "pong"}
