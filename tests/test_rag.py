# /home/dfront/code/dear_future_me/tests/test_rag.py
import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import RagOrchestrator
from app.rag.processor import DocumentProcessor

# from fastapi.testclient import TestClient # Not needed if client is injected
# from app.main import app # Ensure this line is commented out or removed


@pytest.fixture(autouse=True)
def stub_processor(monkeypatch, client: TestClient):  # Add client here if app.dependency_overrides is needed
    monkeypatch.setenv("CHROMA_DIR", "/tmp/chroma_test")
    # stub ingest
    monkeypatch.setattr(DocumentProcessor, "ingest", lambda self, *args, **kwargs: None)

    # stub summary
    async def fake_sum(self, sid):
        return f"SUM for {sid}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_sum)

    # If get_orchestrator is a FastAPI dependency, it should be overridden on the app
    # instance used by the TestClient. The `client` fixture from conftest.py handles this.
    # If get_orchestrator is used directly in tests and needs mocking, that's different.
    # Assuming it's a FastAPI dependency:
    # client.app.dependency_overrides[get_orchestrator] = lambda: RagOrchestrator()
    # However, if RagOrchestrator is initialized globally or differently, this might need adjustment.
    # For now, let's assume the global client fixture handles app-level overrides.
    # If RagOrchestrator is directly instantiated in the route, monkeypatching the class is fine.


def test_ingest_text(client):  # Uses client from conftest.py
    res = client.post("/rag/ingest/", data={"namespace": "theory", "doc_id": "d1", "text": "x"})
    assert res.status_code == 200
    assert res.json()["doc_id"] == "d1"


def test_summarize_session(client):  # Uses client from conftest.py
    sid = "s1"
    res = client.post(f"/rag/session/{sid}/summarize")
    assert res.status_code == 200
    assert res.json()["summary"] == f"SUM for {sid}"


def test_ingest_future_me_namespace(client):  # Uses client from conftest.py
    res = client.post(
        "/rag/ingest/",
        data={
            "namespace": "future_me",
            "doc_id": "fm1",
            "text": "My future self is strong.",
        },
    )
    assert res.status_code == 200
    payload = res.json()
    assert payload["namespace"] == "future_me"
    assert payload["doc_id"] == "fm1"
