# tests/test_auth.py
from fastapi.testclient import TestClient
from app.main import app

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
