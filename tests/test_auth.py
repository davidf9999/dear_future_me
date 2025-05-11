# tests/test_auth.py

import uuid

import pytest
from fastapi.testclient import (
    TestClient,  # Keep this for type hinting if client is passed
)


@pytest.mark.demo_mode(False)  # This test needs registration enabled
def test_register_and_login(client: TestClient):
    # client is now provided by the fixture in conftest.py
    # Generate a unique email
    unique_email = f"test_{uuid.uuid4()}@example.com"

    # Register
    res = client.post("/auth/register", json={"email": unique_email, "password": "secret"})
    print(f"Registration Response Status Code: {res.status_code}")
    print(f"Registration Response Content: {res.json()}")
    assert res.status_code == 201, f"Registration failed: {res.json()}"

    # Login with the newly registered user
    login_res = client.post("/auth/login", data={"username": unique_email, "password": "secret"})
    assert "access_token" in login_res.json(), f"Login failed: {login_res.json()}"
    # # Login temporarily commented out
    # res = client.post(
    #     "/auth/login", data={"username": "a@b.com", "password": "secret"}
    # )
    # assert "access_token" in res.json()
