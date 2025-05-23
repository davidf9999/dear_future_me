# /home/dfront/code/dear_future_me/tests/test_rag_pipeline.py
# Full file content
import os
import uuid  # For unique user emails
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain.retrievers.document_compressors import FlashrankRerank  # For mocking
from langchain_core.documents import Document
from langchain_core.runnables import Runnable  # For mocking retrievers
from langchain_openai import ChatOpenAI  # For mocking

from app.api.orchestrator import RagOrchestrator, get_rag_orchestrator
from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor

# Use the globally mocked settings from conftest.py
settings = get_settings()


@pytest.fixture(scope="module")
def override_chroma_dir(tmp_path_factory) -> Generator[str, None, None]:
    """
    Overrides CHROMA_PERSIST_DIR for the duration of tests in this module
    to use a temporary directory. Cleans up the directory afterwards.
    """
    original_persist_dir = settings.CHROMA_PERSIST_DIR
    temp_dir_obj = tmp_path_factory.mktemp("chroma_pipeline_test_")
    temp_dir = str(temp_dir_obj)

    settings.CHROMA_PERSIST_DIR = temp_dir

    yield temp_dir

    settings.CHROMA_PERSIST_DIR = original_persist_dir


@pytest.fixture
def mock_openai_embeddings(monkeypatch):
    """Mocks OpenAIEmbeddings to prevent actual API calls."""

    class StubEmb:
        def __init__(self, **kwargs):
            pass

        def embed_documents(self, docs):
            return [[0.0] * 10 for _ in docs]

        def embed_query(self, text):
            return [0.0] * 10

    monkeypatch.setattr("app.rag.processor.OpenAIEmbeddings", lambda **kwargs: StubEmb(**kwargs))


def test_document_processor_ingest_and_query(monkeypatch, override_chroma_dir, mock_openai_embeddings):
    class DummyVectorStore:
        def __init__(self, embedding_function, collection_name, persist_directory, client_settings):
            self.docs_store: list[Document] = []
            self.embedding_function = embedding_function
            self.collection_name = collection_name
            self._client_settings = client_settings

        def add_documents(self, documents: list[Document], ids: list[str] | None = None, **kwargs):
            self.docs_store.extend(documents)

        def persist(self):
            pass

        def similarity_search(self, query: str, k: int = 5, **kwargs) -> list[Document]:
            results = [doc for doc in self.docs_store if query.lower() in doc.page_content.lower()]
            return results[:k]

        def _collection(self):
            mock_coll = MagicMock()
            mock_coll.count = MagicMock(return_value=len(self.docs_store))
            return mock_coll

    monkeypatch.setattr(
        "app.rag.processor.Chroma",
        lambda **kwargs: DummyVectorStore(
            embedding_function=kwargs.get("embedding_function"),
            collection_name=kwargs.get("collection_name"),
            persist_directory=kwargs.get("persist_directory"),
            client_settings=kwargs.get("client_settings"),
        ),
    )

    test_namespace = f"test_ns_{os.path.basename(override_chroma_dir)}"
    proc = DocumentProcessor(namespace=test_namespace, persist_directory=override_chroma_dir)

    doc_id1 = "doc1"
    text1 = "This is the first test document."
    proc.ingest(doc_id1, text1)

    doc_id2 = "doc2"
    text2 = "Another document for testing."
    proc.ingest(doc_id2, text2, metadata={"source": "test_source"})

    results = proc.query("first test", k=1)
    assert len(results) == 1
    assert results[0].page_content == text1

    results_meta = proc.query("testing", k=1, metadata_filter={"source": "test_source"})
    assert len(results_meta) == 1
    assert results_meta[0].page_content == text2
    assert results_meta[0].metadata.get("source") == "test_source"


@pytest.mark.asyncio
async def test_singleton_rag_orchestrator_instance(client: TestClient, temp_prompt_files):
    class MockRequest:
        def __init__(self, app):
            self.app = app

    app_instance = client.app
    if hasattr(app_instance.state, "rag_orchestrator_instance"):
        del app_instance.state.rag_orchestrator_instance

    mock_request = MockRequest(app_instance)

    mock_dp_instance_for_singleton = MagicMock(spec=DocumentProcessor)
    mock_dp_instance_for_singleton.vectordb = MagicMock()
    mock_retriever_for_singleton = MagicMock(spec=Runnable)
    mock_retriever_for_singleton.ainvoke = AsyncMock(return_value=[])
    mock_dp_instance_for_singleton.vectordb.as_retriever = MagicMock(return_value=mock_retriever_for_singleton)

    with (
        patch(
            "app.api.orchestrator.DocumentProcessor", return_value=mock_dp_instance_for_singleton
        ),  # Removed as mock_dp_class_patch
        patch("app.api.orchestrator.ChatOpenAI", MagicMock(spec=ChatOpenAI)),  # Removed as mock_llm_class
        patch("app.api.orchestrator.FlashrankRerank", MagicMock(spec=FlashrankRerank)),  # Removed as mock_fr
    ):
        orch1 = await get_rag_orchestrator(request=mock_request)
        orch2 = await get_rag_orchestrator(request=mock_request)

    assert isinstance(orch1, RagOrchestrator)
    assert orch1 is orch2, "RagOrchestrator instances are not the same (singleton test failed)"


@pytest.mark.demo_mode(False)
def test_chat_rag_endpoint(client: TestClient, monkeypatch, temp_prompt_files):
    mock_rag_answer = AsyncMock(
        return_value={"reply": "Mocked RAG response from test_chat_rag_endpoint", "mode": "rag"}
    )

    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_dp_instance.vectordb = MagicMock()
    mock_retriever_instance = MagicMock(spec=Runnable)
    mock_retriever_instance.ainvoke = AsyncMock(return_value=[])
    mock_dp_instance.vectordb.as_retriever = MagicMock(return_value=mock_retriever_instance)

    with (
        patch("app.api.orchestrator.RagOrchestrator.answer", mock_rag_answer),
        patch(
            "app.api.orchestrator.RagOrchestrator.handle_crisis_message",
            AsyncMock(return_value={"reply": "Crisis", "mode": "crisis_rag"}),
        ),
        patch("app.api.orchestrator.DocumentProcessor", return_value=mock_dp_instance),
        patch("app.api.orchestrator.ChatOpenAI", MagicMock(spec=ChatOpenAI)),
        patch("app.api.orchestrator.FlashrankRerank", MagicMock(spec=FlashrankRerank)),
    ):
        test_user_email = f"test_rag_chat_user_{uuid.uuid4().hex[:8]}@example.com"
        test_password = "testpassword"
        client.post("/auth/register", json={"email": test_user_email, "password": test_password})
        login_response = client.post("/auth/login", data={"username": test_user_email, "password": test_password})
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        res = client.post("/chat/text", headers=headers, json={"message": "normal rag query"})

        assert res.status_code == 200
        assert res.json()["reply"] == "Mocked RAG response from test_chat_rag_endpoint"
        mock_rag_answer.assert_called_once()


def test_finalize_session_endpoint(client: TestClient, monkeypatch, temp_prompt_files):
    session_id = "sess123"
    user_id_for_session = "user_for_sess123_pipeline"

    mock_summary_result = ("This is a mocked summary from pipeline.", 5)
    mock_orchestrator_summarize = AsyncMock(return_value=mock_summary_result)

    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_dp_instance.query = AsyncMock(return_value=[])

    with (
        patch("app.api.orchestrator.Orchestrator.summarize_session", mock_orchestrator_summarize),
        patch("app.api.orchestrator.DocumentProcessor", return_value=mock_dp_instance),
        patch("app.api.orchestrator.ChatOpenAI", MagicMock(spec=ChatOpenAI)),
        patch("app.api.orchestrator.FlashrankRerank", MagicMock(spec=FlashrankRerank)),
    ):
        res = client.post(f"/rag/session/{session_id}/summarize?user_id={user_id_for_session}")

    if res.status_code != 200:
        print(f"DEBUG: /rag/session/{session_id}/summarize endpoint failed!")
        print(f"Status Code: {res.status_code}")
        try:
            print(f"Response JSON: {res.json()}")
        except Exception:
            print(f"Response Text (not JSON): {res.text}")

    assert res.status_code == 200
    response_data = res.json()
    assert response_data["summary"] == mock_summary_result[0]
    assert response_data["documents_processed"] == mock_summary_result[1]
    assert response_data["session_id"] == session_id
    mock_orchestrator_summarize.assert_called_once_with(session_id=session_id, user_id=user_id_for_session)
