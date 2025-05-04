# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from pydantic_settings import BaseSettings, Field
from pydantic_settings import BaseSettings, Field

client = TestClient(app)


def test_register_and_login():
    # Register
    res = client.post(
        "/auth/register", json={"email": "a@b.com", "password": "secret"}
    )
    assert res.status_code == 201
    # Login
    res = client.post(
        "/auth/login", data={"username": "a@b.com", "password": "secret"}
    )
    assert "access_token" in res.json()
