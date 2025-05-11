# tests/test_rag_pipeline.py

import uuid

import pytest
from fastapi.testclient import TestClient
from langchain.schema import Document

from app.api.orchestrator import Orchestrator, RagOrchestrator, get_rag_orchestrator

# If current_active_user is solely for test_chat_rag_endpoint, keep its import local or ensure it's mockable
from app.rag.processor import DocumentProcessor

# from app.main import app # app is used by the client fixture


# ─── Fixture: TestClient ─────────────────────────────────────────────
@pytest.fixture
def client_rag_pipeline(client: TestClient):  # Renamed to avoid conflict if there's a global client
    """Uses the global client fixture from conftest.py"""
    return client


# ─── Fixtures to override CHROMA_DIR ─────────────────────────────────
@pytest.fixture(autouse=True)
def override_chroma_dir(tmp_path, monkeypatch):
    # Point Chroma persistence at a temp directory
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma_data"))
    yield


# ─── Test DocumentProcessor ingestion & querying ───────────────────────


def test_document_processor_ingest_and_query(monkeypatch):
    class StubEmb:
        def __init__(self, **kwargs):
            pass

        def embed_documents(self, docs):
            # Return a list of embeddings, one for each document
            return [[0.0] for _ in docs]  # Corrected: should be a list of lists

        def embed_query(self, text):  # Chroma's similarity_search might use embed_query for the query string
            return [0.0]

        # __call__ might be used by older LangChain versions or specific embedding wrapper patterns
        # but embed_documents and embed_query are the primary methods for Chroma.
        # To be safe, if your StubEmb is meant to be a general replacement for OpenAIEmbeddings:
        # def __call__(self, text): # This is often for embedding single queries
        # return [0.0]

    class DummyVectorStore:
        def __init__(self, embedding_function, collection_name, persist_directory):
            self.docs_store = []  # Renamed to avoid confusion with the 'documents' argument
            self.embedding_function = embedding_function  # Store for potential use

        # Updated method signature and logic
        def add_documents(self, documents: list[Document], ids: list[str] | None = None, **kwargs):
            # `documents` is now expected to be a list of LangChain Document objects
            # The real Chroma.add_documents might do more, like creating embeddings internally if not pre-embedded
            # For this dummy, we'll just store them.
            self.docs_store.extend(documents)

        def persist(self):
            pass

        # Updated method logic
        def similarity_search(self, query: str, k: int = 5, **kwargs) -> list[Document]:
            # The dummy logic here is simplified: it doesn't actually use the 'query'
            # or perform a real similarity search. It just returns the first k documents.
            # This was the implicit behavior of the original dummy.
            # If you wanted to make it slightly more realistic, you could use self.embedding_function
            # but for this test, returning stored docs is likely sufficient.
            return self.docs_store[:k]

    monkeypatch.setattr(
        "app.rag.processor.OpenAIEmbeddings",
        lambda **kwargs: StubEmb(**kwargs),  # Pass kwargs
    )
    monkeypatch.setattr(
        "app.rag.processor.Chroma",
        lambda **kwargs: DummyVectorStore(
            embedding_function=kwargs.get("embedding_function"),
            collection_name=kwargs.get("collection_name"),
            persist_directory=kwargs.get("persist_directory"),
        ),
    )

    proc = DocumentProcessor(namespace="test_ns")
    text = "Hello world. Quick test of RAG ingestion."
    # This call should now work with the updated DummyVectorStore
    proc.ingest("doc1", text, metadata={"foo": "bar"})

    results = proc.query("Quick", k=1)
    assert len(results) == 1
    assert isinstance(results[0], Document)  # Good to assert the type
    assert "Hello world. Quick test of RAG ingestion" in results[0].page_content
    if results[0].metadata:  # Check if metadata exists
        assert results[0].metadata.get("foo") == "bar"


# ─── Test get_rag_orchestrator creates a singleton ────────────────────────
def test_singleton_rag_orchestrator_instance():  # Removed client fixture as it's not used
    # Create a mock app state if client.app is not essential,
    # or use client if other app setup is needed.
    # For simplicity, if only app.state is used by get_rag_orchestrator:
    class MockApp:
        def __init__(self):
            self.state = type("S", (), {})()  # Simple object for state

    class DummyReq:
        def __init__(self, app_instance):
            self.app = app_instance

    mock_app_instance = MockApp()
    orch1 = get_rag_orchestrator(DummyReq(mock_app_instance))
    orch2 = get_rag_orchestrator(DummyReq(mock_app_instance))
    assert isinstance(orch1, RagOrchestrator)
    assert orch1 is orch2


# ─── Test /chat/text uses Orchestrator.answer ─────────────────────────


@pytest.mark.demo_mode(False)  # This test needs registration enabled
def test_chat_rag_endpoint(client_rag_pipeline: TestClient, monkeypatch):  # Use the renamed fixture
    # Stub Orchestrator.answer with an async function
    async def fake_answer(self, q):
        return "Echo: " + q

    monkeypatch.setattr(Orchestrator, "answer", fake_answer)

    # Since /chat/text always requires authentication now, we need to register and login a user.
    # 1. Create a test user
    test_user_email = f"test_rag_chat_user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "testpassword"
    register_payload = {"email": test_user_email, "password": test_password}

    reg_response = client_rag_pipeline.post("/auth/register", json=register_payload)
    assert reg_response.status_code == 201, f"Failed to register test user: {reg_response.text}"

    # 2. Log in to get a token
    login_payload = {"username": test_user_email, "password": test_password}
    login_response = client_rag_pipeline.post("/auth/login", data=login_payload)
    assert login_response.status_code == 200, f"Failed to log in test user: {login_response.text}"

    token_data = login_response.json()
    assert "access_token" in token_data, "Access token not found in login response"
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Call the chat endpoint with the token
    res = client_rag_pipeline.post("/chat/text", headers=headers, json={"message": "hi there"})
    assert res.status_code == 200
    assert res.json()["reply"] == "Echo: hi there"


@pytest.fixture(autouse=True)
def stub_summarize(monkeypatch):
    # Stub RagOrchestrator.summarize_session
    async def fake_summarize(self, session_id: str) -> str:
        return f"SUMMARY for {session_id}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_summarize)


def test_finalize_session_endpoint(client_rag_pipeline: TestClient):  # Use the renamed fixture
    session_id = "sess123"
    res = client_rag_pipeline.post(f"/rag/session/{session_id}/summarize")
    assert res.status_code == 200
    payload = res.json()
    assert payload["session_id"] == session_id
    assert payload["summary"] == f"SUMMARY for {session_id}"
