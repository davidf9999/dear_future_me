# /home/dfront/code/dear_future_me/tests/test_rag.py
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.orchestrator import RagOrchestrator
from app.core.settings import get_settings

settings = get_settings()  # Global settings for namespace constants


@pytest.fixture(autouse=True)
def mock_openai_embeddings_for_rag_tests(monkeypatch: pytest.MonkeyPatch):
    """
    Mocks the OpenAIEmbeddings class used by DocumentProcessor.
    Ensures that the mock instance has `embed_documents` and `embed_query`
    methods that return data in the expected format.
    """
    mock_embedding_instance = MagicMock()

    # Configure embed_documents:
    # It's called with a list of texts (strings).
    # It should return a list of embeddings (list of lists of floats).
    # For simplicity, we'll have it return a fixed dummy embedding for each text.
    # The number of dummy embeddings should match the number of texts it receives.
    # The text_splitter in DocumentProcessor might create multiple chunks.
    # Let's make it dynamically return based on the number of input documents.
    def mock_embed_documents(texts: list[str]) -> list[list[float]]:
        # Return a list of dummy embeddings, one for each input text.
        # Each dummy embedding is a list of floats.
        return [[0.1, 0.2, 0.3] for _ in texts]

    mock_embedding_instance.embed_documents = MagicMock(side_effect=mock_embed_documents)

    # Configure embed_query (though not strictly needed for ingest tests, good for completeness):
    # It's called with a single query text (string).
    # It should return a single embedding (list of floats).
    mock_embedding_instance.embed_query = MagicMock(return_value=[0.1, 0.2, 0.3])

    # Patch the class at the location where it's imported by app.rag.processor
    monkeypatch.setattr("app.rag.processor.OpenAIEmbeddings", lambda **kwargs: mock_embedding_instance)


@pytest.fixture(autouse=True)
def skip_if_true_api_key_missing_for_external_tests():
    pass


@pytest.fixture(autouse=True)
def stub_rag_orchestrator_methods(monkeypatch):
    async def mock_summarize_session_for_test(self, session_id: str):
        return f"SUM for {session_id}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", mock_summarize_session_for_test)


def test_ingest_text(client: TestClient):
    namespace_to_test = settings.CHROMA_NAMESPACE_THEORY
    res = client.post(
        "/rag/ingest/", data={"namespace": namespace_to_test, "doc_id": "theory_doc1", "text": "Some theoretical text."}
    )
    assert res.status_code == 200, res.text
    response_json = res.json()
    assert response_json["doc_id"] == "theory_doc1"
    assert response_json["namespace"] == namespace_to_test


def test_summarize_session(client: TestClient):
    sid = "s1_rag_test"
    res = client.post(f"/rag/session/{sid}/summarize")
    assert res.status_code == 200, res.text
    response_json = res.json()
    assert response_json["summary"] == f"SUM for {sid}"


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
