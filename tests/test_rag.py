# tests/test_rag.py
import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import RagOrchestrator, get_orchestrator
from app.main import app
from app.rag.processor import DocumentProcessor


@pytest.fixture(autouse=True)
def stub_processor(monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", "/tmp/chroma_test")

    # Correctly mock the ingest method signature to accept keyword arguments
    # or use *args, **kwargs if specific argument names are not needed by the mock.
    def mock_ingest(self, *args, **kwargs):  # Changed to *args, **kwargs
        # This mock does nothing, just ensures the call signature is correct
        # when called with keyword arguments like document_id='...'
        pass

    monkeypatch.setattr(DocumentProcessor, "ingest", mock_ingest)

    async def fake_sum(self, sid):
        return f"SUM for {sid}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_sum)
    app.dependency_overrides[get_orchestrator] = lambda: RagOrchestrator()


@pytest.fixture
def client():
    return TestClient(app)


def test_ingest_text(client):
    # The API endpoint extracts doc_id from the filename
    res = client.post(
        "/rag/ingest/",
        data={"namespace": "theory"},
        files={"file": ("test_doc.txt", b"This is the content of the test document.")},
    )
    assert res.status_code == 201
    assert "Document 'test_doc.txt' ingested into namespace 'theory' successfully." in res.json()["message"]


def test_summarize_session(client):
    sid = "s1"
    res = client.post(f"/rag/session/{sid}/summarize")
    assert res.status_code == 200
    assert res.json()["session_id"] == sid
    assert res.json()["summary"] == f"SUM for {sid}"


def test_ingest_future_me_namespace(client):
    res = client.post(
        "/rag/ingest/",
        data={
            "namespace": "future_me",
        },
        files={"file": ("future_me_doc.txt", b"My future self is strong.")},
    )
    assert res.status_code == 201
    payload = res.json()
    assert "Document 'future_me_doc.txt' ingested into namespace 'future_me' successfully." in payload["message"]
