# tests/test_chat.py
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_public_chat_endpoint():
    """
    Chat endpoints are public in DEMO_MODE, so no auth needed.
    """
    resp = client.post("/chat/text", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json()["reply"].lower().startswith("echo")
