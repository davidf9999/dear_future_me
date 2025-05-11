# tests/test_chat.py
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import Orchestrator

# from app.main import app # app is used by the client fixture


@pytest.mark.asyncio
@pytest.mark.demo_mode(False)  # This test needs registration enabled
async def test_chat_endpoint_authenticated(client: TestClient, monkeypatch):
    """
    Tests the /chat/text endpoint with an authenticated user.
    The endpoint now always requires authentication.
    """

    async def mock_answer(self, message: str):
        return f"echo: {message}"

    monkeypatch.setattr(Orchestrator, "answer", mock_answer)

    # 1. Create a test user
    test_user_email = f"test_chat_user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "testpassword"
    register_payload = {"email": test_user_email, "password": test_password}

    # Ensure the app is fully initialized for the test client context
    # This is usually handled by TestClient(app) but let's be explicit if issues persist
    with client as current_client:  # Use the client fixture
        reg_response = current_client.post("/auth/register", json=register_payload)
        assert reg_response.status_code == 201, f"Failed to register test user: {reg_response.text}"

        # 2. Log in to get a token
        login_payload = {"username": test_user_email, "password": test_password}
        login_response = current_client.post("/auth/login", data=login_payload)
        assert login_response.status_code == 200, f"Failed to log in test user: {login_response.text}"

        token_data = login_response.json()
        assert "access_token" in token_data, "Access token not found in login response"
        token = token_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Call the chat endpoint with the token
        resp = current_client.post("/chat/text", headers=headers, json={"message": "hello"})
        assert resp.status_code == 200

        reply_data = resp.json()
        assert "reply" in reply_data, "Reply key not found in chat response"
        assert reply_data["reply"].lower().startswith("echo:")
