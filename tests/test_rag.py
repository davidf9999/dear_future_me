# /home/dfront/code/dear_future_me/tests/test_rag.py
# Full file content
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import RagOrchestrator
from app.core.settings import get_settings

settings = get_settings()


@pytest.fixture(autouse=True)
def mock_openai_embeddings_for_rag_tests(monkeypatch: pytest.MonkeyPatch):
    mock_embedding_instance = MagicMock()

    def mock_embed_documents(texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    mock_embedding_instance.embed_documents = MagicMock(side_effect=mock_embed_documents)
    mock_embedding_instance.embed_query = MagicMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr("app.rag.processor.OpenAIEmbeddings", lambda **kwargs: mock_embedding_instance)


@pytest.fixture(autouse=True)
def skip_if_true_api_key_missing_for_external_tests():
    pass  # Placeholder, actual skip logic might be more complex


@pytest.fixture(autouse=True)
def stub_rag_orchestrator_methods(monkeypatch):
    # This stubs the method on the RagOrchestrator class itself.
    # If a test needs to verify the *internal* logic of summarize_session,
    # that test should be in test_orchestrator.py and mock dependencies of summarize_session.
    async def mock_summarize_session_for_rag_endpoint_test(self, session_id: str):
        # This mock is for testing the /rag/session/{session_id}/summarize endpoint connectivity
        # and basic request/response structure, not the summarization logic itself.
        return f"SUMMARY for {session_id} (from rag_test stub)"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", mock_summarize_session_for_rag_endpoint_test)


def test_ingest_text(client: TestClient):
    namespace_to_test = settings.CHROMA_NAMESPACE_THEORY
    res = client.post(
        "/rag/ingest/", data={"namespace": namespace_to_test, "doc_id": "theory_doc1", "text": "Some theoretical text."}
    )
    assert res.status_code == 200, res.text
    response_json = res.json()
    assert response_json["doc_id"] == "theory_doc1"
    assert response_json["namespace"] == namespace_to_test


def test_ingest_session_data_with_session_id(client: TestClient):
    namespace_to_test = settings.CHROMA_NAMESPACE_SESSION_DATA
    doc_id_val = "transcript_part1"
    session_id_val = "session_abc_123"

    # Mock DocumentProcessor to check metadata
    # This requires the client fixture to patch DocumentProcessor for this specific test's scope
    # or ensure that the global DocumentProcessor mock (if any from conftest) can be inspected.
    # For simplicity, we'll assume the endpoint passes it correctly and rely on DocumentProcessor's own tests
    # for metadata handling. Here, we just check the API response.

    res = client.post(
        "/rag/ingest/",
        data={
            "namespace": namespace_to_test,
            "doc_id": doc_id_val,
            "text": "User: Hello. AI: Hi there!",
            "session_id": session_id_val,  # Pass the session_id
        },
    )
    assert res.status_code == 200, res.text
    response_json = res.json()
    assert response_json["doc_id"] == doc_id_val
    assert response_json["namespace"] == namespace_to_test
    # We can't directly assert metadata content from the API response here,
    # but we trust the endpoint logic to pass it to DocumentProcessor.
    # More detailed metadata checks would involve mocking DocumentProcessor.ingest
    # specifically for this test or inspecting the ChromaDB instance if not mocked.


def test_summarize_session_endpoint_connectivity(client: TestClient):
    # This test now relies on the stub_rag_orchestrator_methods fixture
    # which mocks RagOrchestrator.summarize_session.
    sid = "s1_rag_test"
    res = client.post(f"/rag/session/{sid}/summarize")
    assert res.status_code == 200, res.text
    response_json = res.json()
    assert response_json["session_id"] == sid
    assert response_json["summary"] == f"SUMMARY for {sid} (from rag_test stub)"


def test_ingest_future_me_namespace(client: TestClient):
    namespace_to_test = settings.CHROMA_NAMESPACE_FUTURE_ME
    res = client.post(
        "/rag/ingest/",
        data={
            "namespace": namespace_to_test,
            "doc_id": "fm_user1",
            "text": "My future self is resilient and kind.",
        },
    )
    assert res.status_code == 200, res.text
    payload = res.json()
    assert payload["namespace"] == namespace_to_test
    assert payload["doc_id"] == "fm_user1"
