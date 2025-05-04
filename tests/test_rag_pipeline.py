import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.rag.processor import DocumentProcessor
from app.api.orchestrator import (
    RagOrchestrator,
    get_rag_orchestrator,
    Orchestrator,
    get_orchestrator,
)
from app.api.chat import current_active_user


# ─── Fixture: TestClient ─────────────────────────────────────────────
@pytest.fixture
def client():
    return TestClient(app)


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
            return [[0.0]] * len(docs)

        def __call__(self, text):
            return [0.0]

    class DummyVectorStore:
        def __init__(self, embedding_function, collection_name, persist_directory):
            self.docs = []

        def add_documents(self, docs):
            self.docs = docs

        def persist(self):
            pass

        def similarity_search(self, q, k):
            from langchain.schema import Document

            return [
                Document(page_content=d["text"], metadata=d.get("metadata"))
                for d in self.docs[:k]
            ]

    monkeypatch.setattr(
        "app.rag.processor.OpenAIEmbeddings", lambda **kwargs: StubEmb()
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
    assert "Quick test of RAG ingestion" in results[0].page_content


# ─── Test get_rag_orchestrator creates a singleton ────────────────────────
def test_singleton_rag_orchestrator_instance(client):
    DummyReq = type("R", (), {"app": client.app})
    orch1 = get_rag_orchestrator(DummyReq())
    orch2 = get_rag_orchestrator(DummyReq())
    assert isinstance(orch1, RagOrchestrator)
    assert orch1 is orch2


# ─── Test /chat/text uses Orchestrator.answer ───────────────────────── ─────────────────────────


def test_chat_rag_endpoint(monkeypatch, client):
    # Stub Orchestrator.answer with an async function
    async def fake_answer(self, q):
        return "Echo: " + q

    monkeypatch.setattr(Orchestrator, "answer", fake_answer)
    from app.auth.router import fastapi_users

    # Override simple orchestrator
    client.app.dependency_overrides[get_orchestrator] = lambda: Orchestrator()
    # Override auth dependency from app.api.chat
    client.app.dependency_overrides[current_active_user] = lambda: type(
        "U", (), {"is_active": True}
    )()

    res = client.post(
        "/chat/text",
        json={"message": "hi there"},
        headers={"Authorization": "Bearer testtoken"},
    )
    assert res.status_code == 200
    assert res.json()["reply"] == "Echo: hi there"


@pytest.fixture(autouse=True)
def stub_summarize(monkeypatch):
    # Stub RagOrchestrator.summarize_session
    async def fake_summarize(self, session_id: str) -> str:
        return f"SUMMARY for {session_id}"

    monkeypatch.setattr(RagOrchestrator, "summarize_session", fake_summarize)


def test_finalize_session_endpoint(client):
    session_id = "sess123"
    res = client.post(f"/rag/session/{session_id}/summarize")
    assert res.status_code == 200
    payload = res.json()
    assert payload["session_id"] == session_id
    assert payload["summary"] == f"SUMMARY for {session_id}"
