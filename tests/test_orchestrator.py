# tests/test_orchestrator.py
# Full file content
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from langchain.retrievers.document_compressors import FlashrankRerank
from langchain_core.documents import Document  # For creating mock documents
from langchain_core.prompt_values import StringPromptValue  # Corrected import path
from langchain_core.runnables import Runnable  # For mocking retrievers
from langchain_openai import ChatOpenAI  # For mocking

from app.api.models import UserData
from app.api.orchestrator import Orchestrator, RagOrchestrator
from app.core.settings import Settings, get_settings
from app.rag.processor import DocumentProcessor  # For type hinting

# Use the globally mocked settings from conftest.py
# This ensures that tests use the test-specific configurations.
test_settings = get_settings()


@pytest.fixture
def mock_settings() -> Settings:
    """Returns the globally mocked settings instance from conftest."""
    return test_settings


@pytest.fixture
def mock_document_processor():
    """Mocks DocumentProcessor and its methods."""
    mock_dp = MagicMock(spec=DocumentProcessor)
    mock_dp.query = MagicMock(return_value=[])  # Default to no docs found

    mock_dp.vectordb = MagicMock()
    mock_retriever = MagicMock(spec=Runnable)
    mock_retriever.ainvoke = AsyncMock(return_value=[])
    mock_retriever.invoke = MagicMock(return_value=[])  # Add invoke for synchronous calls
    mock_dp.vectordb.as_retriever = MagicMock(return_value=mock_retriever)
    return mock_dp


@pytest.fixture
def mock_llm():
    """Mocks the ChatOpenAI instance."""
    mock_llm_instance = MagicMock(spec=ChatOpenAI)
    mock_llm_instance.ainvoke = AsyncMock(return_value="Mocked LLM Response")
    return mock_llm_instance


@pytest.fixture
def rag_orchestrator(
    mock_settings: Settings, temp_prompt_files, mock_document_processor: MagicMock, mock_llm: MagicMock
):
    """Provides a RagOrchestrator instance with mocked dependencies."""
    with (
        patch("app.api.orchestrator.FlashrankRerank", MagicMock(spec=FlashrankRerank)),
        patch("app.api.orchestrator.DocumentProcessor", return_value=mock_document_processor),
        patch("app.api.orchestrator.ChatOpenAI", return_value=mock_llm),
    ):
        orchestrator = RagOrchestrator(settings=mock_settings)
        orchestrator.theory_db = mock_document_processor
        orchestrator.personal_plan_db = mock_document_processor
        orchestrator.session_data_db = mock_document_processor
        orchestrator.future_me_db = mock_document_processor
        orchestrator.therapist_notes_db = mock_document_processor
        orchestrator.chat_summaries_db = mock_document_processor
        return orchestrator


@pytest.fixture
def main_orchestrator(mock_settings: Settings, rag_orchestrator: RagOrchestrator, temp_prompt_files):
    """Provides the main Orchestrator with a mocked RagOrchestrator."""
    with patch.object(Orchestrator, "_get_rag_orchestrator", return_value=rag_orchestrator):
        orchestrator = Orchestrator(settings=mock_settings)
        orchestrator.rag_orchestrator = rag_orchestrator
        yield orchestrator


# --- RagOrchestrator Tests ---


@pytest.mark.asyncio
async def test_rag_orchestrator_has_all_dbs(rag_orchestrator: RagOrchestrator):
    """Tests that RagOrchestrator initializes all required DocumentProcessor instances."""
    assert rag_orchestrator.theory_db is not None
    assert rag_orchestrator.personal_plan_db is not None
    assert rag_orchestrator.session_data_db is not None
    assert rag_orchestrator.future_me_db is not None
    assert rag_orchestrator.therapist_notes_db is not None
    assert rag_orchestrator.chat_summaries_db is not None


@pytest.mark.asyncio
async def test_rag_orchestrator_get_combined_retriever_uses_ensemble(rag_orchestrator: RagOrchestrator):
    """Tests that _get_combined_retriever returns an EnsembleRetriever."""
    from langchain.retrievers import EnsembleRetriever

    retriever = rag_orchestrator._get_combined_retriever(user_id="test_user")
    assert isinstance(retriever, EnsembleRetriever)
    assert len(retriever.retrievers) > 1

    retriever_no_user = rag_orchestrator._get_combined_retriever(user_id=None)
    assert isinstance(retriever_no_user, EnsembleRetriever)
    assert len(retriever_no_user.retrievers) == 1


@pytest.mark.asyncio
async def test_orchestrator_rag_path_uses_ensemble_retriever_and_formats_docs(
    rag_orchestrator: RagOrchestrator, mock_document_processor: MagicMock
):
    """Tests the RAG path, ensuring the ensemble retriever is used and docs are formatted."""
    rag_orchestrator.llm.ainvoke.return_value = "LLM RAG response"

    # Create a mock Document with actual string page_content
    mock_lc_document = Document(page_content="Test document content", metadata={"doc_id": "test_doc_1"})

    mock_base_retriever_instance = MagicMock(spec=Runnable)
    mock_base_retriever_instance.ainvoke = AsyncMock(return_value=[mock_lc_document])  # Return list of Document
    mock_document_processor.vectordb.as_retriever.return_value = mock_base_retriever_instance

    with patch.object(rag_orchestrator, "_format_docs", wraps=rag_orchestrator._format_docs) as spy_format_docs:
        await rag_orchestrator.answer("User query", user_id="test_user")
        spy_format_docs.assert_called_once()
        rag_orchestrator.llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_includes_user_data_in_prompt(rag_orchestrator: RagOrchestrator):
    rag_orchestrator.llm.ainvoke.return_value = "LLM response with user data"

    user_data_dict = {"name": "Test User", "preferences": "likes concise answers"}
    user_data_model = UserData(**user_data_dict)

    await rag_orchestrator.answer("A question", user_id="test_user", user_data=user_data_model)

    rag_orchestrator.llm.ainvoke.assert_called_once()
    # The input to ChatOpenAI.ainvoke is a PromptValue, not a dict
    prompt_value_arg = rag_orchestrator.llm.ainvoke.call_args[0][0]

    # Convert PromptValue to messages or string to inspect
    # Assuming system_prompt is a ChatPromptTemplate, it will produce ChatPromptValue
    prompt_messages = prompt_value_arg.to_messages()
    full_prompt_text = " ".join([msg.content for msg in prompt_messages])

    assert "Test User" in full_prompt_text
    assert "likes concise answers" in full_prompt_text


@pytest.mark.asyncio
async def test_rag_orchestrator_crisis_chain_uses_personal_plan_rag(
    rag_orchestrator: RagOrchestrator, mock_document_processor: MagicMock
):
    rag_orchestrator.llm.ainvoke.return_value = "Crisis response using personal plan"

    mock_personal_plan_doc = Document(
        page_content="Personal crisis plan content.", metadata={"doc_id": "plan1", "user_id": "crisis_user"}
    )

    personal_plan_retriever_mock = MagicMock(spec=Runnable)
    # get_crisis_retriever uses .invoke()
    personal_plan_retriever_mock.invoke = MagicMock(return_value=[mock_personal_plan_doc])

    rag_orchestrator.personal_plan_db.vectordb.as_retriever.return_value = personal_plan_retriever_mock

    user_data_model = UserData(name="Crisis User")
    await rag_orchestrator.handle_crisis_message("I need help now", user_id="crisis_user", user_data=user_data_model)

    rag_orchestrator.llm.ainvoke.assert_called_once()
    # Assert that the synchronous 'invoke' was called on the retriever mock
    personal_plan_retriever_mock.invoke.assert_called_with("I need help now")

    call_args = rag_orchestrator.llm.ainvoke.call_args[0][0]
    prompt_messages = call_args.to_messages()
    full_prompt_text = " ".join([msg.content for msg in prompt_messages])

    assert "Personal crisis plan content." in full_prompt_text


@pytest.mark.asyncio
async def test_summarize_session_retrieves_and_summarizes_data(
    rag_orchestrator: RagOrchestrator, mock_document_processor: MagicMock
):
    """Tests that summarize_session retrieves docs and calls LLM for summarization."""
    rag_orchestrator.llm.ainvoke.return_value = "Session summary."
    # Use Document instances for mock_docs
    mock_docs = [
        Document(page_content="Line 1", metadata={"session_id": "test_session_123", "user_id": "test_user_abc"}),
        Document(page_content="Line 2", metadata={"session_id": "test_session_123", "user_id": "test_user_abc"}),
    ]
    mock_document_processor.query = MagicMock(return_value=mock_docs)

    summary, count = await rag_orchestrator.summarize_session("test_session_123", "test_user_abc")

    assert count == 2
    assert summary == "Session summary."
    mock_document_processor.query.assert_called_once_with(
        query="", k=1000, metadata_filter={"session_id": "test_session_123", "user_id": "test_user_abc"}
    )
    rag_orchestrator.llm.ainvoke.assert_called_once()

    # The input to the summarization chain's LLM is a dict {"transcript": ...}
    # which then gets formatted by PromptTemplate into a StringPromptValue.
    prompt_value_arg = rag_orchestrator.llm.ainvoke.call_args[0][0]
    assert isinstance(prompt_value_arg, StringPromptValue)
    prompt_text = prompt_value_arg.to_string()

    assert "Line 1" in prompt_text
    assert "Line 2" in prompt_text


@pytest.mark.asyncio
async def test_summarize_session_no_docs_found(rag_orchestrator: RagOrchestrator, mock_document_processor: MagicMock):
    """Tests summarize_session when no documents are found."""
    mock_document_processor.query = MagicMock(return_value=[])

    summary, count = await rag_orchestrator.summarize_session("test_session_empty", "test_user_empty")

    assert count == 0
    assert summary is None
    mock_document_processor.query.assert_called_once_with(
        query="", k=1000, metadata_filter={"session_id": "test_session_empty", "user_id": "test_user_empty"}
    )


@pytest.mark.asyncio
async def test_summarize_session_query_error(rag_orchestrator: RagOrchestrator, mock_document_processor: MagicMock):
    """Tests summarize_session when DocumentProcessor.query raises an error."""
    mock_document_processor.query = MagicMock(side_effect=Exception("DB query failed"))
    # No need to assign to rag_orchestrator.session_data_db if the class is patched in rag_orchestrator fixture

    with pytest.raises(HTTPException) as exc_info:
        await rag_orchestrator.summarize_session("test_session_err", "test_user_err")

    assert exc_info.value.status_code == 500
    assert "Error retrieving session data" in exc_info.value.detail


# --- Main Orchestrator Tests ---


@pytest.mark.asyncio
async def test_orchestrator_crisis_mode(main_orchestrator: Orchestrator, rag_orchestrator: RagOrchestrator):
    """Tests that the main orchestrator switches to crisis mode."""
    rag_orchestrator.handle_crisis_message = AsyncMock(return_value={"reply": "Crisis response", "mode": "crisis_rag"})

    crisis_message = "I want to end it all."
    response = await main_orchestrator.answer(crisis_message, user_id="test_user")

    assert response["mode"] == "crisis_rag"
    assert response["reply"] == "Crisis response"
    rag_orchestrator.handle_crisis_message.assert_called_once_with(crisis_message, "test_user", None)


@pytest.mark.asyncio
async def test_orchestrator_rag_mode(main_orchestrator: Orchestrator, rag_orchestrator: RagOrchestrator):
    """Tests that the main orchestrator uses RAG mode for normal messages."""
    rag_orchestrator.answer = AsyncMock(return_value={"reply": "RAG response", "mode": "rag"})

    normal_message = "Tell me about CBT."
    user_data = UserData(name="Test User")
    response = await main_orchestrator.answer(normal_message, user_id="test_user", user_data=user_data, session_id="s1")

    assert response["mode"] == "rag"
    assert response["reply"] == "RAG response"
    rag_orchestrator.answer.assert_called_once_with(normal_message, "test_user", user_data, "s1")


@pytest.mark.asyncio
async def test_orchestrator_fails_if_prompt_file_missing(mock_settings: Settings, mock_document_processor: MagicMock):
    """Tests that Orchestrator (and RagOrchestrator) fails if a prompt template is missing."""
    mock_llm_class = MagicMock(spec=ChatOpenAI)  # Mock the class
    mock_flashrank_class = MagicMock(spec=FlashrankRerank)  # Mock the class

    original_system_prompt_file = mock_settings.SYSTEM_PROMPT_FILE
    mock_settings.SYSTEM_PROMPT_FILE = "non_existent_prompt.md"

    with (
        pytest.raises(FileNotFoundError),
        patch("app.api.orchestrator.ChatOpenAI", mock_llm_class),
        patch("app.api.orchestrator.FlashrankRerank", mock_flashrank_class),
        patch("app.api.orchestrator.DocumentProcessor", return_value=mock_document_processor),
    ):
        RagOrchestrator(settings=mock_settings)

    mock_settings.SYSTEM_PROMPT_FILE = original_system_prompt_file

    original_crisis_prompt_file = mock_settings.CRISIS_PROMPT_FILE
    mock_settings.CRISIS_PROMPT_FILE = "non_existent_crisis_prompt.md"

    with (
        pytest.raises(FileNotFoundError),
        patch("app.api.orchestrator.ChatOpenAI", mock_llm_class),
        patch("app.api.orchestrator.FlashrankRerank", mock_flashrank_class),
        patch("app.api.orchestrator.DocumentProcessor", return_value=mock_document_processor),
    ):
        orchestrator = Orchestrator(settings=mock_settings)
        await orchestrator.answer("I am in crisis", user_id="test_user")

    mock_settings.CRISIS_PROMPT_FILE = original_crisis_prompt_file
