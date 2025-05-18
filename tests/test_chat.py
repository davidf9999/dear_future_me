# /home/dfront/code/dear_future_me/tests/test_chat.py
import uuid

import pytest
from fastapi.testclient import TestClient  # Keep this for type hinting

from app.api.orchestrator import Orchestrator

# from app.main import app # Ensure this line is commented out or removed if present


@pytest.mark.asyncio
@pytest.mark.demo_mode(False)  # This test needs registration enabled
async def test_chat_endpoint_authenticated(client: TestClient, monkeypatch):  # Uses client from conftest.py
    """
    Tests the /chat/text endpoint with an authenticated user.
    The endpoint now always requires authentication.
    """

    async def mock_answer(self, message: str):
        return {"reply": f"echo: {message}"}  # Return a dictionary

    monkeypatch.setattr(Orchestrator, "answer", mock_answer)

    # 1. Create a test user
    test_user_email = f"test_chat_user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "testpassword"
    register_payload = {"email": test_user_email, "password": test_password}

    reg_response = client.post("/auth/register", json=register_payload)
    assert reg_response.status_code == 201, f"Failed to register test user: {reg_response.text}"

    # 2. Log in to get a token
    login_payload = {"username": test_user_email, "password": test_password}
    login_response = client.post("/auth/login", data=login_payload)
    assert login_response.status_code == 200, f"Failed to log in test user: {login_response.text}"

    token_data = login_response.json()
    assert "access_token" in token_data, "Access token not found in login response"
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Call the chat endpoint with the token
    resp = client.post("/chat/text", headers=headers, json={"message": "hello"})
    if resp.status_code != 200:
        print("DEBUG: /chat/text endpoint failed!")
        print(f"Status Code: {resp.status_code}")
        try:
            print(f"Response JSON: {resp.json()}")
        except Exception:
            print(f"Response Text (not JSON): {resp.text}")
    assert resp.status_code == 200

    reply_data = resp.json()
    assert "reply" in reply_data, "Reply key not found in chat response"
    assert reply_data["reply"].lower().startswith("echo:")
