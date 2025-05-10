# tests/test_chat.py
import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import Orchestrator
from app.main import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_public_chat_endpoint(monkeypatch):
    """
    Chat endpoints are public in DEMO_MODE, so no auth needed.
    """

    async def mock_answer(self, message: str):
        return f"echo: {message}"

    monkeypatch.setattr(Orchestrator, "answer", mock_answer)

    resp = client.post("/chat/text", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json()["reply"].lower().startswith("echo:")
