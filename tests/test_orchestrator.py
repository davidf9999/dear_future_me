# /home/dfront/code/dear_future_me/tests/test_orchestrator.py
import logging
import uuid  # Import uuid
from typing import Any, Dict, Literal
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from langchain.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.orchestrator import BranchingChain, Orchestrator, RagOrchestrator
from app.core.settings import Settings
from app.db.models import UserProfileTable  # For type hinting in tests
from app.rag.processor import DocumentProcessor


# Fixture to mock ChatOpenAI for all tests in this file
@pytest.fixture(autouse=True)
def mock_chat_openai(monkeypatch):
    mock_llm_instance = MagicMock(spec=ChatOpenAI)
    mock_llm_instance.invoke = MagicMock(return_value="Mocked LLM response")
    mock_llm_instance.ainvoke = AsyncMock(return_value="Mocked LLM async response")

    monkeypatch.setattr("app.api.orchestrator.ChatOpenAI", lambda **kwargs: mock_llm_instance)
    return mock_llm_instance


# Fixture to mock DocumentProcessor to prevent actual ChromaDB/Embedding calls
@pytest.fixture(autouse=True)
def mock_document_processor(monkeypatch):
    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_vectordb = MagicMock()
    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)
    mock_retriever_instance.get_relevant_documents = MagicMock(return_value=[])
    mock_retriever_instance.aget_relevant_documents = AsyncMock(return_value=[])
    mock_vectordb.as_retriever.return_value = mock_retriever_instance
    mock_dp_instance.vectordb = mock_vectordb
    # Ensure the lambda accepts the 'namespace' argument and any other potential kwargs
    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda namespace, **kwargs: mock_dp_instance)
    return mock_dp_instance


@pytest.mark.asyncio
async def test_non_risk_uses_rag_chain(monkeypatch, mock_chat_openai):
    mock_rag_sub_chain_ainvoke_result = {"reply_content": "RAG→OK", "sources": []}

    mock_runnable_returned_by_builder = AsyncMock(spec=Runnable)
    mock_runnable_returned_by_builder.ainvoke = AsyncMock(return_value=mock_rag_sub_chain_ainvoke_result)

    with patch.object(
        RagOrchestrator, "_build_actual_rag_chain", return_value=mock_runnable_returned_by_builder
    ) as mock_rag_builder_method:
        orch = RagOrchestrator()
        monkeypatch.setattr(orch, "_detect_risk", lambda query: False)

        # Mock get_user_profile to return None (no profile found) for this specific test if needed
        # or a mock profile if specific profile data is required for the base prompt.
        # For simplicity, assume no profile or default values are handled by get_user_specific_prompt_str.
        mock_get_profile = AsyncMock(return_value=None)
        monkeypatch.setattr("app.api.orchestrator.get_user_profile", mock_get_profile)

        mock_db_session = MagicMock(spec=AsyncSession)
        response = await orch.answer("hello", user_id=str(uuid.uuid4()), db_session=mock_db_session)

        assert response == {"reply": "RAG→OK"}
        mock_rag_builder_method.assert_called_once()
        assert isinstance(mock_rag_builder_method.call_args[0][0], ChatPromptTemplate)
        assert mock_rag_builder_method.call_args[0][1] is orch.llm
        assert isinstance(mock_rag_builder_method.call_args[0][2], BaseRetriever)

        mock_runnable_returned_by_builder.ainvoke.assert_called_once_with({"input": "hello"})


@pytest.mark.asyncio
async def test_risk_uses_crisis_chain(monkeypatch, mock_chat_openai):
    mock_crisis_sub_chain_ainvoke_result = {"reply_content": "CRISIS!!!"}

    mock_runnable_returned_by_builder = AsyncMock(spec=Runnable)
    mock_runnable_returned_by_builder.ainvoke = AsyncMock(return_value=mock_crisis_sub_chain_ainvoke_result)

    with patch.object(
        Orchestrator, "_build_crisis_chain", return_value=mock_runnable_returned_by_builder
    ) as mock_crisis_builder_method:
        orch = Orchestrator()
        monkeypatch.setattr(orch, "_detect_risk", lambda query: True)

        mock_get_profile = AsyncMock(return_value=None)
        monkeypatch.setattr("app.api.orchestrator.get_user_profile", mock_get_profile)

        mock_db_session = MagicMock(spec=AsyncSession)
        response = await orch.answer("I want to die", user_id=str(uuid.uuid4()), db_session=mock_db_session)

        assert response == {"reply": "CRISIS!!!"}
        mock_crisis_builder_method.assert_called_once()
        assert isinstance(mock_crisis_builder_method.call_args[0][0], ChatPromptTemplate)
        assert mock_crisis_builder_method.call_args[0][1] is orch.llm
        mock_runnable_returned_by_builder.ainvoke.assert_called_once_with({"query": "I want to die", "context": []})


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch, mock_chat_openai):
    orch = Orchestrator()

    mock_branching_chain = AsyncMock(spec=BranchingChain)
    mock_branching_chain.ainvoke.side_effect = RuntimeError("Simulated chain error")
    orch.chain = mock_branching_chain

    mock_get_profile = AsyncMock(return_value=None)  # Mock profile call
    monkeypatch.setattr("app.api.orchestrator.get_user_profile", mock_get_profile)

    mock_db_session = MagicMock(spec=AsyncSession)
    response = await orch.answer("anything", user_id=str(uuid.uuid4()), db_session=mock_db_session)
    assert response == {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}


@pytest.mark.asyncio
async def test_answer_uses_user_specific_prompts(monkeypatch, mock_chat_openai):
    # Create a mock UserProfileTable object
    mock_user_profile_obj = MagicMock(spec=UserProfileTable)
    mock_user_profile_obj.name = "Test User"
    mock_user_profile_obj.future_me_persona_summary = "Custom future me summary for test_user."
    mock_user_profile_obj.key_therapeutic_language = "Custom therapeutic phrases."
    mock_user_profile_obj.core_values_summary = "Custom core values."
    mock_user_profile_obj.safety_plan_summary = "Custom safety plan summary."  # Add if used

    # Mock the get_user_profile CRUD function to return this object
    mock_get_user_profile_crud = AsyncMock(return_value=mock_user_profile_obj)
    monkeypatch.setattr("app.api.orchestrator.get_user_profile", mock_get_user_profile_crud)

    mock_rag_sub_chain_ainvoke_result = {"reply_content": "RAG response with custom prompt", "sources": []}
    mock_runnable_returned_by_builder = AsyncMock(spec=Runnable)
    mock_runnable_returned_by_builder.ainvoke = AsyncMock(return_value=mock_rag_sub_chain_ainvoke_result)

    with patch.object(
        RagOrchestrator, "_build_actual_rag_chain", return_value=mock_runnable_returned_by_builder
    ) as mock_rag_builder_method:
        orch = RagOrchestrator()
        # Ensure the base template string has the placeholders for this test
        # This is crucial for the personalization to be injected correctly.
        orch.base_system_prompt_template_str = (
            "Base system prompt. Hello {name}. Future Me: {future_me_persona_summary}. "
            "Language: {critical_language_elements}. Values: {core_values_prompt}. "
            "Safety: {safety_plan_summary}. "  # Add if used
            "Context: {context} Input: {input}"
        )
        monkeypatch.setattr(orch, "_detect_risk", lambda query: False)

        test_user_uuid = uuid.uuid4()
        mock_db_session = MagicMock(spec=AsyncSession)
        await orch.answer("hello", user_id=str(test_user_uuid), db_session=mock_db_session)

        mock_get_user_profile_crud.assert_called_with(mock_db_session, user_id=test_user_uuid)

        mock_rag_builder_method.assert_called_once()
        captured_chat_prompt_template_obj = mock_rag_builder_method.call_args[0][0]

        assert captured_chat_prompt_template_obj is not None
        assert isinstance(captured_chat_prompt_template_obj, ChatPromptTemplate)

        assert len(captured_chat_prompt_template_obj.messages) >= 1
        first_message_prompt = captured_chat_prompt_template_obj.messages[0]
        # The type of message can vary based on ChatPromptTemplate.from_template internal logic
        # It's often HumanMessagePromptTemplate or SystemMessagePromptTemplate
        assert hasattr(first_message_prompt, "prompt") and hasattr(first_message_prompt.prompt, "template")

        actual_template_string = first_message_prompt.prompt.template

        assert "Hello Test User." in actual_template_string
        assert "Custom future me summary for test_user." in actual_template_string
        assert "Custom therapeutic phrases." in actual_template_string
        assert "Custom core values." in actual_template_string
        assert "Custom safety plan summary." in actual_template_string
        assert "Base system prompt." in actual_template_string
        assert "Context: {context} Input: {input}" in actual_template_string


@pytest.mark.asyncio
async def test_summarize_session_success(monkeypatch, mock_chat_openai):
    orch = RagOrchestrator()
    mock_chat_openai.ainvoke = AsyncMock(return_value="SESSION SUMMARY")

    assert await orch.summarize_session("sess1") == "SESSION SUMMARY"


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch, mock_chat_openai):
    orch = RagOrchestrator()
    mock_chat_openai.ainvoke = AsyncMock(side_effect=RuntimeError("Simulated LLM error for summarization"))

    assert await orch.summarize_session("sessX") == "Summary for sessX (unavailable)"


def test_rag_orchestrator_has_future_db(mock_document_processor):
    orch = RagOrchestrator()
    assert hasattr(orch, "future_db"), "RagOrchestrator must have future_db"
    assert isinstance(orch.future_db, MagicMock)
    assert orch.future_db is mock_document_processor


def test_detect_risk_functionality(mock_chat_openai):
    orch = Orchestrator()
    assert orch._detect_risk("I want to die") is True
    assert orch._detect_risk("I feel HOPELESS sometimes") is True
    assert orch._detect_risk("I am happy today") is False
    assert orch._detect_risk("") is False


def create_mock_settings(lang: Literal["en", "he"], **kwargs: Any) -> Settings:
    defaults: Dict[str, Any] = {
        "DATABASE_URL": "sqlite+aiosqlite:///./test_lang.db",
        "SECRET_KEY": "testsecret",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 60,
        "DEMO_MODE": True,
        "DEBUG_SQL": False,
        "MAX_MESSAGE_LENGTH": 1000,
        "ASR_TIMEOUT_SECONDS": 15.0,
        "CHROMA_DIR": "./chroma_test_lang",
        "CHROMA_NAMESPACE_THEORY": "theory",
        "CHROMA_NAMESPACE_PLAN": "personal_plan",
        "CHROMA_NAMESPACE_SESSION": "session_data",
        "CHROMA_NAMESPACE_FUTURE": "future_me",
        "CHROMA_NAMESPACE_THERAPIST_NOTES": "therapist_notes",  # Added
        "CHROMA_NAMESPACE_CHAT_HISTORY": "dfm_chat_history_summaries",  # Added
        "OPENAI_API_KEY": "test_api_key_for_settings",
        "LLM_MODEL": "gpt-4o",
        "LLM_TEMPERATURE": 0.7,
        "DEMO_USER_EMAIL": "demo@example.com",
        "DEMO_USER_PASSWORD": "password",
        "APP_DEFAULT_LANGUAGE": lang,
        "DFM_API_HOST": "0.0.0.0",
        "DFM_API_PORT": 8000,
        "STREAMLIT_SERVER_PORT": 8501,
        "SKIP_AUTH": False,
        "STREAMLIT_DEBUG": False,
    }
    final_args = {**defaults, **kwargs}
    return Settings(**final_args)


@pytest.mark.parametrize(
    "lang_setting, he_files_exist, en_files_exist, expected_base_crisis_content, expected_base_system_content, expect_warning",
    [
        ("he", True, True, "Hebrew Crisis Prompt", "Hebrew System Prompt", False),
        ("he", False, True, "English Crisis Prompt", "English System Prompt", True),
        ("en", False, True, "English Crisis Prompt", "English System Prompt", False),
        (
            "he",
            False,
            False,
            "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}",
            "Hello {name}. I am your future self. Persona: {future_me_persona_summary}. Language: {critical_language_elements}. Values: {core_values_prompt}. Safety: {safety_plan_summary}. Based on the following context: {context} Answer the question: {input}",
            True,
        ),  # Updated default system prompt expectation
        (
            "en",
            False,
            False,
            "You are a crisis responder. Respond with empathy and provide resources. Context: {context} Query: {query}",
            "Hello {name}. I am your future self. Persona: {future_me_persona_summary}. Language: {critical_language_elements}. Values: {core_values_prompt}. Safety: {safety_plan_summary}. Based on the following context: {context} Answer the question: {input}",
            True,
        ),  # Updated default system prompt expectation
    ],
)
def test_orchestrator_prompt_loading_by_language(
    monkeypatch: pytest.MonkeyPatch,
    lang_setting: Literal["en", "he"],
    he_files_exist: bool,
    en_files_exist: bool,
    expected_base_crisis_content: str,
    expected_base_system_content: str,
    expect_warning: bool,
    mock_chat_openai,
    mock_document_processor,
):
    mock_settings = create_mock_settings(lang=lang_setting)
    monkeypatch.setattr("app.api.orchestrator.get_settings", lambda: mock_settings)

    def mock_path_exists(path: str) -> bool:
        if lang_setting == "he":
            if path == "templates/crisis_prompt.he.md" or path == "templates/system_prompt.he.md":
                return he_files_exist
        if path == "templates/crisis_prompt.md" or path == "templates/system_prompt.md":
            return en_files_exist
        if path == f"templates/crisis_prompt.{lang_setting}.md" and lang_setting != "he":
            return en_files_exist
        if path == f"templates/system_prompt.{lang_setting}.md" and lang_setting != "he":
            return en_files_exist
        return False

    monkeypatch.setattr("app.api.orchestrator.os.path.exists", mock_path_exists)

    file_contents: Dict[str, str] = {}
    if he_files_exist:
        file_contents["templates/crisis_prompt.he.md"] = "Hebrew Crisis Prompt"
        file_contents["templates/system_prompt.he.md"] = "Hebrew System Prompt"
    if en_files_exist:
        file_contents["templates/crisis_prompt.md"] = "English Crisis Prompt"
        file_contents["templates/system_prompt.md"] = "English System Prompt"
        file_contents["templates/crisis_prompt.en.md"] = "English Crisis Prompt"
        file_contents["templates/system_prompt.en.md"] = "English System Prompt"

    def open_side_effect(path: str, *args: Any, **kwargs: Any) -> Any:
        if path in file_contents:
            return mock_open(read_data=file_contents[path])(*args, **kwargs)
        if not he_files_exist and not en_files_exist and ("crisis_prompt" in path or "system_prompt" in path):
            raise FileNotFoundError(f"Mocked FileNotFoundError for {path}")
        raise FileNotFoundError(f"Mocked FileNotFoundError for unhandled path: {path}")

    monkeypatch.setattr("builtins.open", open_side_effect)

    with patch("app.api.orchestrator.logging.warning") as mock_log_warning:
        orch_instance = Orchestrator()

        # For the hardcoded default system prompt, ensure the test expectation matches the actual default in Orchestrator
        if not he_files_exist and not en_files_exist:
            # Match the actual default in Orchestrator, which now includes safety_plan_summary
            expected_base_system_content = (
                "Hello {name}. I am your future self. "
                "Persona: {future_me_persona_summary}. "
                "Language: {critical_language_elements}. "
                "Values: {core_values_prompt}. "
                "Safety: {safety_plan_summary}. "
                "Based on the following context: {context} Answer the question: {input}"
            )

        assert expected_base_crisis_content in orch_instance.base_crisis_prompt_template_str
        assert expected_base_system_content in orch_instance.base_system_prompt_template_str

        if expect_warning:
            was_warning_called_for_fallback = False
            for call_args in mock_log_warning.call_args_list:
                if call_args[0] and isinstance(call_args[0][0], str):
                    log_message = call_args[0][0]
                    if "Falling back to generic" in log_message or "Using hardcoded default" in log_message:
                        was_warning_called_for_fallback = True
                        break
            assert was_warning_called_for_fallback, "Expected fallback/hardcoded warning not logged"
        else:
            unexpected_fallback_logged = False
            for call_args_tuple in mock_log_warning.call_args_list:
                if call_args_tuple and call_args_tuple[0] and isinstance(call_args_tuple[0][0], str):
                    log_message = call_args_tuple[0][0]
                    if "Falling back to" in log_message or "Using hardcoded default" in log_message:
                        unexpected_fallback_logged = True
                        logging.error(f"Unexpected warning logged: {log_message}")
                        break
            assert not unexpected_fallback_logged, (
                f"Unexpected fallback/hardcoded warning logged: {mock_log_warning.call_args_list}"
            )


# Note: CRUD tests for UserProfileTable and API tests for /user_profile/
# should ideally be in their own files (e.g., tests/test_crud/test_user_profile_crud.py
# and tests/test_api/test_user_profile_api.py) for better organization.
# For this response, they are omitted from test_orchestrator.py to keep it focused.
# If you had them here previously and want them back, they would need to be added.
