import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(autouse=True)
def override_orch(monkeypatch):
    # Dummy orchestrator for chat
    class DummyOrch:
        async def answer(self, q):
            return "Echo: " + q

    from app.api.chat import get_orchestrator

    app.dependency_overrides[get_orchestrator] = lambda: DummyOrch()

    # Bypass auth
    from app.auth.router import fastapi_users

    app.dependency_overrides[fastapi_users.current_user(active=True)] = lambda: type(
        "U", (), {"is_active": True}
    )()


@pytest.fixture
def client():
    return TestClient(app)


def test_text_chat_authenticated(client):
    # register & login …
    client.post("/auth/register", json={"email": "a@b.com", "password": "secret"})
    tok = client.post(
        "/auth/login", data={"username": "a@b.com", "password": "secret"}
    ).json()["access_token"]
    res = client.post(
        "/chat/text", json={"message": "hi"}, headers={"Authorization": f"Bearer {tok}"}
    )
    assert res.status_code == 200
    assert res.json() == {"reply": "Echo: hi"}
