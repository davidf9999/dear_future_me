# tests/test_orchestrator.py

import logging  # For capturing log messages
from typing import Any, Dict, List, Literal  # Import Literal, Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, mock_open

import pytest
from langchain.prompts import ChatPromptTemplate  # For mocking its class method
from langchain_core.retrievers import BaseRetriever  # For mocking retriever

from app.api.orchestrator import BranchingChain, Orchestrator, RagOrchestrator
from app.core.settings import Settings  # Import Settings for mocking
from app.rag.processor import DocumentProcessor  # For mocking


@pytest.mark.asyncio
async def test_non_risk_uses_rag_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: False)

    mock_rag_chain = AsyncMock()
    # Ensure the mock returns the expected dictionary structure
    mock_rag_chain.ainvoke = AsyncMock(return_value={"answer": "RAG→OK"})

    monkeypatch.setattr(orch, "_rag_chain", mock_rag_chain)
    # CRUCIAL FIX: Re-initialize orch.chain to use the mocked _rag_chain
    orch.chain = BranchingChain(orch._detect_risk, orch._crisis_chain, orch._rag_chain)

    response = await orch.answer("hello")
    assert response == {"reply": "RAG→OK"}


@pytest.mark.asyncio
async def test_risk_uses_crisis_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: True)

    mock_crisis_chain = AsyncMock()
    # Ensure the mock returns the expected dictionary structure
    mock_crisis_chain.ainvoke = AsyncMock(return_value={"result": "CRISIS!!!"})

    monkeypatch.setattr(orch, "_crisis_chain", mock_crisis_chain)
    # CRUCIAL FIX: Re-initialize orch.chain to use the mocked _crisis_chain
    orch.chain = BranchingChain(orch._detect_risk, orch._crisis_chain, orch._rag_chain)

    response = await orch.answer("I want to die")
    assert response == {"reply": "CRISIS!!!"}


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch):
    orch = Orchestrator()

    mock_branching_chain = AsyncMock()
    mock_branching_chain.ainvoke.side_effect = RuntimeError("Simulated chain error")

    monkeypatch.setattr(orch, "chain", mock_branching_chain)
    response = await orch.answer("anything")
    assert response == {"reply": "I’m sorry, I’m unable to answer that right now. Please try again later."}


@pytest.mark.asyncio
async def test_summarize_session_success(monkeypatch):
    orch = RagOrchestrator()
    mock_summarize_chain = AsyncMock()
    # summarize_chain with StrOutputParser now returns a string directly
    mock_summarize_chain.ainvoke = AsyncMock(return_value="SESSION SUMMARY")

    monkeypatch.setattr(orch, "summarize_chain", mock_summarize_chain)

    assert await orch.summarize_session("sess1") == "SESSION SUMMARY"


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch):
    orch = RagOrchestrator()
    mock_summarize_chain = AsyncMock()
    mock_summarize_chain.ainvoke.side_effect = RuntimeError("Simulated chain error")

    monkeypatch.setattr(orch, "summarize_chain", mock_summarize_chain)

    assert await orch.summarize_session("sessX") == "Summary for sessX (unavailable)"


def test_rag_orchestrator_has_future_db():
    orch = RagOrchestrator()
    assert hasattr(orch, "future_db"), "RagOrchestrator must have future_db"
    from app.rag.processor import (
        DocumentProcessor as ActualDocProcessor,  # Avoid name clash
    )

    assert isinstance(orch.future_db, ActualDocProcessor)


def test_detect_risk_functionality():
    orch = Orchestrator()  # Uses default lang for keywords
    assert orch._detect_risk("I want to die") is True
    assert orch._detect_risk("I feel HOPELESS sometimes") is True
    assert orch._detect_risk("I am happy today") is False
    assert orch._detect_risk("") is False
    # Note: This test uses English keywords. If APP_DEFAULT_LANGUAGE is "he",
    # and _risk_keywords are not updated for Hebrew, this test might behave
    # differently than intended for Hebrew risk detection. For Phase 1, this is acceptable.


# --- Tests for Language Support in Orchestrator ---


# Helper to create a mock Settings object
def create_mock_settings(lang: Literal["en", "he"], **kwargs: Any) -> Settings:
    # Provide default values for all required fields in Settings
    # to avoid validation errors when instantiating.
    # Adjust these defaults if your Settings model changes.
    # Ensure values in this dictionary have the correct Python types.
    defaults: Dict[str, Any] = {
        "DATABASE_URL": "sqlite+aiosqlite:///./test_lang.db",
        "SECRET_KEY": "testsecret",
        "ACCESS_TOKEN_EXPIRE_MINUTES": 60,  # Already an int
        "DEMO_MODE": True,  # Already a bool
        "DEBUG_SQL": False,  # Already a bool
        "MAX_MESSAGE_LENGTH": 1000,  # Already an int
        "ASR_TIMEOUT_SECONDS": 15.0,  # Already a float
        "CHROMA_DIR": "./chroma_test_lang",
        "CHROMA_NAMESPACE_THEORY": "theory",
        "CHROMA_NAMESPACE_PLAN": "personal_plan",
        "CHROMA_NAMESPACE_SESSION": "session_data",
        "CHROMA_NAMESPACE_FUTURE": "future_me",
        "OPENAI_API_KEY": "test_api_key",
        "LLM_MODEL": "gpt-4o",
        "LLM_TEMPERATURE": 0.7,  # Already a float
        "DEMO_USER_EMAIL": "demo@example.com",
        "DEMO_USER_PASSWORD": "password",
        "APP_DEFAULT_LANGUAGE": lang,  # Type is Literal["en", "he"]
    }
    # Update defaults with any kwargs passed by the test
    # This ensures kwargs take precedence if a key is in both.
    final_args = {**defaults, **kwargs}

    # Pydantic will perform its own validation at runtime.
    # This ignore is for Mypy's static analysis struggling with **dict unpacking into Pydantic models.
    return Settings(**final_args)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "lang_setting, he_files_exist, en_files_exist, expected_crisis_content, expected_system_content, expect_warning",
    [
        ("he", True, True, "Hebrew Crisis Prompt", "Hebrew System Prompt", False),
        ("he", False, True, "English Crisis Prompt", "English System Prompt", True),  # Fallback
        ("en", False, True, "English Crisis Prompt", "English System Prompt", False),  # English default
        # Edge case: No English files either (Orchestrator should use hardcoded default strings)
        ("he", False, False, "You are a crisis responder.", "Based on the following context:", True),
        (
            "en",
            False,
            False,
            "You are a crisis responder.",
            "Based on the following context:",
            True,
        ),  # Warning because specific en.md not found
    ],
)
def test_orchestrator_prompt_loading_by_language(
    monkeypatch: pytest.MonkeyPatch,  # Added type hint for monkeypatch
    lang_setting: Literal["en", "he"],  # Added type hint
    he_files_exist: bool,  # Added type hint
    en_files_exist: bool,  # Added type hint
    expected_crisis_content: str,  # Added type hint
    expected_system_content: str,  # Added type hint
    expect_warning: bool,  # Added type hint
):
    # 1. Mock get_settings
    mock_settings = create_mock_settings(lang=lang_setting)
    monkeypatch.setattr("app.api.orchestrator.get_settings", lambda: mock_settings)

    # 2. Mock os.path.exists
    def mock_path_exists(path: str) -> bool:  # Added type hint
        if lang_setting == "he":
            if path == "templates/crisis_prompt.he.md" or path == "templates/system_prompt.he.md":
                return he_files_exist
        # For lang_setting=="en", or fallback checks for .md files
        if path == "templates/crisis_prompt.md" or path == "templates/system_prompt.md":
            return en_files_exist
        # If lang_setting=="en" and we check for *.en.md, assume they don't exist for this test
        # unless we add another parameter for it. For now, *.md is the English default.
        if path == f"templates/crisis_prompt.{lang_setting}.md" and lang_setting != "he":  # e.g. crisis_prompt.en.md
            return en_files_exist  # Assuming *.en.md is the same as *.md for simplicity here
        if path == f"templates/system_prompt.{lang_setting}.md" and lang_setting != "he":  # e.g. system_prompt.en.md
            return en_files_exist
        return False  # Default for any other path

    monkeypatch.setattr("app.api.orchestrator.os.path.exists", mock_path_exists)

    # 3. Mock builtins.open
    file_contents: Dict[str, str] = {}
    if he_files_exist:
        file_contents["templates/crisis_prompt.he.md"] = "Hebrew Crisis Prompt"
        file_contents["templates/system_prompt.he.md"] = "Hebrew System Prompt"
    if en_files_exist:
        file_contents["templates/crisis_prompt.md"] = "English Crisis Prompt"
        file_contents["templates/system_prompt.md"] = "English System Prompt"
        # If testing for specific *.en.md files, add them here too
        file_contents["templates/crisis_prompt.en.md"] = "English Crisis Prompt"
        file_contents["templates/system_prompt.en.md"] = "English System Prompt"

    # m_open = mock_open() # We will create fresh mocks inside the side_effect
    def open_side_effect(path: str, *args: Any, **kwargs: Any) -> Any:  # Added type hints
        if path in file_contents:
            # Return a new mock_open object configured with the specific read_data for this path
            return mock_open(read_data=file_contents[path])(*args, **kwargs)
        # If no files exist at all, Orchestrator uses hardcoded defaults
        if not he_files_exist and not en_files_exist and ("crisis_prompt" in path or "system_prompt" in path):
            # This simulates FileNotFoundError for prompt files, triggering internal defaults
            raise FileNotFoundError(f"Mocked FileNotFoundError for {path}")
        # For any other unexpected file open, raise an error to catch issues
        # print(f"Warning: Mock open called for unexpected path: {path}")
        raise FileNotFoundError(f"Mocked FileNotFoundError for unhandled path: {path}")

    monkeypatch.setattr("builtins.open", open_side_effect)

    # 4. Mock ChatPromptTemplate.from_template
    # We want to capture the string content passed to from_template
    actual_prompt_contents_passed: List[str] = []
    original_from_template = ChatPromptTemplate.from_template

    def mock_from_template_capture(template_content_str: str, **kwargs: Any) -> ChatPromptTemplate:  # Added type hints
        actual_prompt_contents_passed.append(template_content_str)
        # Return a ChatPromptTemplate that includes expected variables
        # to satisfy internal chain validations.
        # The crisis chain prompt uses {context} and {query}
        # The RAG chain prompt uses {context} and {input}
        if "crisis_prompt" in template_content_str.lower() or (
            expected_crisis_content and expected_crisis_content.lower() in template_content_str.lower()
        ):
            return original_from_template(template="dummy crisis {context} {query}", **kwargs)
        return original_from_template(template="dummy rag {context} {input}", **kwargs)

    monkeypatch.setattr(ChatPromptTemplate, "from_template", mock_from_template_capture)

    # 5. Mock logging.warning
    mock_log_warning = MagicMock()
    monkeypatch.setattr(logging, "warning", mock_log_warning)  # Patch logging at module level used by orchestrator

    # 6. Mock DocumentProcessor to avoid its __init__ side effects (ChromaDB, embeddings)
    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_vectordb = MagicMock()

    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)
    mock_retriever_instance.get_relevant_documents = MagicMock(return_value=[])
    mock_retriever_instance.aget_relevant_documents = AsyncMock(return_value=[])  # type: ignore[method-assign]
    mock_vectordb.as_retriever.return_value = mock_retriever_instance
    mock_dp_instance.vectordb = mock_vectordb
    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda ns: mock_dp_instance)

    # 7. Instantiate Orchestrator - this will trigger the prompt loading
    Orchestrator()

    # 8. Assertions
    assert len(actual_prompt_contents_passed) >= 2, (
        f"ChatPromptTemplate.from_template not called enough times. Called {len(actual_prompt_contents_passed)} times. Content: {actual_prompt_contents_passed}"
    )

    assert any(expected_crisis_content in content for content in actual_prompt_contents_passed), (
        f"Expected crisis content '{expected_crisis_content}' not found in {actual_prompt_contents_passed}"
    )

    assert any(expected_system_content in content for content in actual_prompt_contents_passed), (
        f"Expected system content '{expected_system_content}' not found in {actual_prompt_contents_passed}"
    )

    if expect_warning:
        assert mock_log_warning.called, "Expected logging.warning to be called for fallback"
    else:
        unexpected_fallback_logged = False
        for call_args_tuple in mock_log_warning.call_args_list:
            # call_args_tuple is like ((arg1, arg2,...), {kwarg1: val1,...})
            # or just (arg1, arg2,...) if no kwargs
            # We are interested in the first positional argument of the log call
            if call_args_tuple and call_args_tuple[0]:  # Check if there are positional args
                log_message = call_args_tuple[0][0]
                if isinstance(log_message, str) and "Falling back to" in log_message:
                    unexpected_fallback_logged = True
                    break
        assert not unexpected_fallback_logged, f"Unexpected fallback warning logged: {mock_log_warning.call_args_list}"
