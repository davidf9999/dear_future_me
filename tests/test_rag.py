import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rag.processor import DocumentProcessor
from app.api.orchestrator import get_rag_orchestrator, RagOrchestrator


@pytest.fixture(autouse=True)
def stub_processor(monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", "/tmp/chroma_test")
    # stub ingest
    monkeypatch.setattr(DocumentProcessor, "ingest", lambda self, *args, **kwargs: None)

    # stub summary
    async def fake_sum(self, sid):
        return f"SUM for {sid}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_sum)
    # override dependency
    app.dependency_overrides[get_rag_orchestrator] = lambda: RagOrchestrator()


@pytest.fixture
def client():
    return TestClient(app)


def test_ingest_text(client):
    res = client.post(
        "/rag/ingest/", data={"namespace": "theory", "doc_id": "d1", "text": "x"}
    )
    assert res.status_code == 200
    assert res.json()["doc_id"] == "d1"


def test_summarize_session(client):
    sid = "s1"
    res = client.post(f"/rag/session/{sid}/summarize")
    assert res.status_code == 200
    assert res.json()["summary"] == f"SUM for {sid}"


def test_ingest_future_me_namespace(client):
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