# tests/test_rag.py
# Full file content
import logging
import os
import shutil
import tempfile
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from langchain_openai import OpenAIEmbeddings  # For mocking

from app.core.settings import get_settings
from app.rag.processor import DocumentProcessor  # For type hinting

# Use the globally mocked settings from conftest.py
settings = get_settings()


@pytest.fixture(scope="module")
def temp_chroma_dir() -> Generator[str, None, None]:
    """
    Creates a temporary directory for Chroma data for this test module.
    Overrides the CHROMA_PERSIST_DIR setting.
    """
    original_persist_dir = settings.CHROMA_PERSIST_DIR
    temp_dir = tempfile.mkdtemp(prefix="chroma_rag_test_")
    settings.CHROMA_PERSIST_DIR = temp_dir
    logging.info(f"Overriding CHROMA_PERSIST_DIR to: {temp_dir} for test_rag.py module")

    yield temp_dir  # Provide the path if needed by tests

    settings.CHROMA_PERSIST_DIR = original_persist_dir  # Restore
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    logging.info(f"Cleaned up temp Chroma dir: {temp_dir} and restored CHROMA_PERSIST_DIR")


# This fixture ensures that DocumentProcessor uses the temp_chroma_dir for its persistence
@pytest.fixture(autouse=True)  # Apply to all tests in this file
def mock_doc_processor_dependencies_for_rag_tests(temp_chroma_dir, monkeypatch):
    """
    Patches DocumentProcessor.__init__ to ensure it uses the temp_chroma_dir
    for persist_directory when CHROMA_HOST/PORT are not set (local mode).
    Also mocks OpenAIEmbeddings to prevent actual API calls.
    """
    original_init = DocumentProcessor.__init__

    def new_init(
        self,
        namespace,
        embedding_model=settings.EMBEDDING_MODEL,
        persist_directory=None,
        chroma_host=None,
        chroma_port=None,
    ):
        effective_persist_dir = persist_directory
        if not (chroma_host or chroma_port):
            effective_persist_dir = temp_chroma_dir

        original_init(
            self,
            namespace=namespace,
            embedding_model=embedding_model,
            persist_directory=effective_persist_dir,
            chroma_host=chroma_host,
            chroma_port=chroma_port,
        )

    monkeypatch.setattr(DocumentProcessor, "__init__", new_init)

    # Mock OpenAIEmbeddings to prevent API calls during ingestion tests
    mock_embeddings = MagicMock(spec=OpenAIEmbeddings)
    mock_embeddings.embed_documents = MagicMock(return_value=[[0.1, 0.2, 0.3]] * 1)  # Example embedding
    mock_embeddings.embed_query = MagicMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr("app.rag.processor.OpenAIEmbeddings", lambda **kwargs: mock_embeddings)


def test_ingest_text(client: TestClient, temp_chroma_dir):  # temp_chroma_dir ensures setup
    namespace_to_test = settings.CHROMA_NAMESPACE_THEORY
    res = client.post(
        "/rag/ingest/", data={"namespace": namespace_to_test, "doc_id": "theory_doc1", "text": "Some theoretical text."}
    )
    assert res.status_code == 200, res.text
    response_data = res.json()
    assert response_data["status"] == "ok"
    assert response_data["namespace"] == namespace_to_test
    assert response_data["doc_id"] == "theory_doc1"


def test_ingest_session_data_with_session_id(client: TestClient, temp_chroma_dir):
    namespace_to_test = settings.CHROMA_NAMESPACE_SESSION_DATA
    doc_id_val = "transcript_part1"
    session_id_val = "session_abc_123"

    res = client.post(
        "/rag/ingest/",
        data={
            "namespace": namespace_to_test,
            "doc_id": doc_id_val,
            "text": "User: Hello. AI: Hi there!",
            "session_id": session_id_val,
        },
    )
    assert res.status_code == 200, res.text
    response_data = res.json()
    assert response_data["status"] == "ok"
    assert response_data["namespace"] == namespace_to_test
    assert response_data["doc_id"] == doc_id_val


def test_summarize_session_endpoint_connectivity(
    client: TestClient, monkeypatch, temp_prompt_files
):  # Added temp_prompt_files from conftest
    sid = "s1_rag_test"
    user_id_for_session = "user_for_s1_rag_test"

    mock_summary_result = ("Mocked summary from test_rag", 1)
    mock_orchestrator_summarize = AsyncMock(return_value=mock_summary_result)

    with patch("app.api.orchestrator.Orchestrator.summarize_session", mock_orchestrator_summarize):
        res = client.post(f"/rag/session/{sid}/summarize?user_id={user_id_for_session}")

    assert res.status_code == 200, res.text
    response_data = res.json()
    assert response_data["summary"] == mock_summary_result[0]
    assert response_data["documents_processed"] == mock_summary_result[1]
    assert response_data["session_id"] == sid
    mock_orchestrator_summarize.assert_called_once_with(session_id=sid, user_id=user_id_for_session)


def test_ingest_future_me_namespace(client: TestClient, temp_chroma_dir):
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
    response_data = res.json()
    assert response_data["status"] == "ok"
    assert response_data["namespace"] == namespace_to_test
    assert response_data["doc_id"] == "fm_user1"
