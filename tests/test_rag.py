# tests/test_rag.py

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rag.processor import DocumentProcessor
from app.api.orchestrator import RagOrchestrator, get_orchestrator


@pytest.fixture(autouse=True)
def stub_processor(monkeypatch):
    """
    Stub ingestion so we don't touch Chroma, stub summarization
    so we don't call an LLM, and wire get_orchestrator to use RagOrchestrator.
    """

    # 1) Stub DocumentProcessor.ingest
    def fake_ingest(self, doc_id, text, metadata=None):
        return None

    monkeypatch.setattr(DocumentProcessor, "ingest", fake_ingest)

    # 2) Stub RagOrchestrator.summarize_session
    async def fake_summarize(self, session_id: str) -> str:
        return f"SUMMARY for {session_id}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_summarize)

    # 3) Override get_orchestrator dependency to return our RagOrchestrator
    app.dependency_overrides[get_orchestrator] = lambda: RagOrchestrator()

    yield

    # Cleanup after tests
    app.dependency_overrides.pop(get_orchestrator, None)


@pytest.fixture
def client():
    return TestClient(app)


def test_ingest_text(client):
    response = client.post(
        "/rag/ingest/",
        data={
            "namespace": "theory",
            "doc_id": "doc123",
            "text": "Sentence one. Sentence two.",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "namespace": "theory",
        "doc_id": "doc123",
    }


def test_ingest_file(tmp_path, client):
    # Write a temp file to upload
    file_path = tmp_path / "test.txt"
    file_path.write_text("File sentence A. File sentence B.")
    with open(file_path, "rb") as f:
        response = client.post(
            "/rag/ingest/",
            data={"namespace": "session_data", "doc_id": "file1"},
            files={"file": ("test.txt", f, "text/plain")},
        )
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "namespace": "session_data",
        "doc_id": "file1",
    }


def test_summarize_session(client):
    session_id = "sess007"
    response = client.post(f"/rag/session/{session_id}/summarize")
    assert response.status_code == 200

    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["summary"] == f"SUMMARY for {session_id}"
