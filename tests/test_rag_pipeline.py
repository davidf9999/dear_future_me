# /home/dfront/code/dear_future_me/tests/test_rag_pipeline.py
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient  # Keep this for type hinting
from langchain_core.documents import Document

from app.api.orchestrator import Orchestrator, RagOrchestrator, get_orchestrator
from app.rag.processor import DocumentProcessor

# from app.main import app # Ensure this line is commented out or removed


# ─── Fixtures to override CHROMA_DIR ─────────────────────────────────
@pytest.fixture(autouse=True)
def override_chroma_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma_data"))
    yield


# ─── Test DocumentProcessor ingestion & querying ───────────────────────


def test_document_processor_ingest_and_query(monkeypatch):
    class StubEmb:
        def __init__(self, **kwargs):
            pass

        def embed_documents(self, docs):
            return [[0.0] for _ in docs]

        def embed_query(self, text):
            return [0.0]

    class DummyVectorStore:
        def __init__(self, embedding_function, collection_name, persist_directory):
            self.docs_store: list[Document] = []
            self.embedding_function = embedding_function

        def add_documents(self, documents: list[Document], ids: list[str] | None = None, **kwargs):
            self.docs_store.extend(documents)

        def persist(self):
            pass

        def similarity_search(self, query: str, k: int = 5, **kwargs) -> list[Document]:
            return self.docs_store[:k]

    monkeypatch.setattr(
        "app.rag.processor.OpenAIEmbeddings",
        lambda **kwargs: StubEmb(**kwargs),
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
    proc.ingest("doc1", text, metadata={"foo": "bar"})

    results = proc.query("Quick", k=1)
    assert len(results) == 1
    assert isinstance(results[0], Document)
    assert "Hello world. Quick test of RAG ingestion" in results[0].page_content
    if results[0].metadata:
        assert results[0].metadata.get("foo") == "bar"


# ─── Test get_orchestrator creates a singleton ────────────────────────
@pytest.mark.asyncio
async def test_singleton_rag_orchestrator_instance(client: TestClient):  # Add client if app state is needed
    # If get_orchestrator relies on app.state from the TestClient's app:
    # orch1 = await get_orchestrator(client.app) # This assumes get_orchestrator takes the app
    # orch2 = await get_orchestrator(client.app)
    # For now, assuming the previous MockApp structure was for a unit test not needing the full client.
    # If get_orchestrator is a FastAPI dependency, it's handled by the client fixture.
    # This test might need rethinking if it's for testing the dependency injection via FastAPI.
    class MockApp:  # Keeping this for now if it's a unit-style test for get_orchestrator
        def __init__(self):
            self.state = type("S", (), {})()

    class DummyReq:  # If get_orchestrator expects a Request object
        def __init__(self, app_instance: Any):
            self.app = app_instance
            self.state = app_instance.state  # Make app state accessible via request.state

    mock_app_instance = MockApp()
    # If get_orchestrator expects a request object:
    dummy_request = DummyReq(mock_app_instance)
    orch1 = await get_orchestrator(request=dummy_request)  # Pass as keyword if signature is (request: Request)
    orch2 = await get_orchestrator(request=dummy_request)

    assert isinstance(orch1, RagOrchestrator)
    assert orch1 is orch2


# ─── Test /chat/text uses Orchestrator.answer ─────────────────────────


@pytest.mark.demo_mode(False)
def test_chat_rag_endpoint(client: TestClient, monkeypatch):
    async def fake_answer(self, q):
        return {"reply": "Echo: " + q}

    monkeypatch.setattr(Orchestrator, "answer", fake_answer)

    test_user_email = f"test_rag_chat_user_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "testpassword"
    register_payload = {"email": test_user_email, "password": test_password}

    reg_response = client.post("/auth/register", json=register_payload)
    assert reg_response.status_code == 201, f"Failed to register test user: {reg_response.text}"

    login_payload = {"username": test_user_email, "password": test_password}
    login_response = client.post("/auth/login", data=login_payload)
    assert login_response.status_code == 200, f"Failed to log in test user: {login_response.text}"

    token_data = login_response.json()
    assert "access_token" in token_data, "Access token not found in login response"
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.post("/chat/text", headers=headers, json={"message": "hi there"})
    assert res.status_code == 200
    assert res.json()["reply"] == "Echo: hi there"


@pytest.fixture(autouse=True)
def stub_summarize(monkeypatch):
    async def fake_summarize(self, session_id: str) -> str:
        return f"SUMMARY for {session_id}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_summarize)


def test_finalize_session_endpoint(client: TestClient):
    session_id = "sess123"
    res = client.post(f"/rag/session/{session_id}/summarize")
    if res.status_code != 200:
        print(f"DEBUG: /rag/session/{session_id}/summarize endpoint failed!")
        print(f"Status Code: {res.status_code}")
        try:
            print(f"Response JSON: {res.json()}")
        except Exception:
            print(f"Response Text (not JSON): {res.text}")
    assert res.status_code == 200
    payload = res.json()
    assert payload["session_id"] == session_id
    assert payload["summary"] == f"SUMMARY for {session_id}"
