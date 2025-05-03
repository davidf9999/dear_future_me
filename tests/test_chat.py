# tests/test_chat.py
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def override_orchestrator(monkeypatch):
    # 1) Ensure OPENAI_API_KEY is set so Orchestrator.__init__ won't blow up:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-123")

    # 2) Create a dummy orchestrator
    class DummyOrch:
        async def answer(self, query: str) -> str:
            return "Echo: " + query

    # 3) Override the FastAPI dependency
    from app.api.chat import get_orchestrator

    app.dependency_overrides[get_orchestrator] = lambda: DummyOrch()


def test_text_chat_authenticated():
    client = TestClient(app)
    # Register & login to get JWT token…
    client.post("/auth/register", json={"email": "a@b.com", "password": "secret"})
    login = client.post(
        "/auth/login", data={"username": "a@b.com", "password": "secret"}
    )
    token = login.json()["access_token"]

    # Now our /chat/text uses DummyOrch, never LangChain!
    res = client.post(
        "/chat/text",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    assert res.json() == {"reply": "Echo: hello"}
