# /home/dfront/code/dear_future_me/tests/test_orchestrator.py

import logging  # For capturing log messages
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
    mock_rag_chain.ainvoke = AsyncMock(return_value={"answer": "RAG→OK"})

    monkeypatch.setattr(orch, "_rag_chain", mock_rag_chain)
    # CRUCIAL FIX: Re-initialize orch.chain to use the mocked _rag_chain
    orch.chain = BranchingChain(orch._detect_risk, orch._crisis_chain, orch._rag_chain)

    assert await orch.answer("hello") == "RAG→OK"


@pytest.mark.asyncio
async def test_risk_uses_crisis_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: True)

    mock_crisis_chain = AsyncMock()
    mock_crisis_chain.ainvoke = AsyncMock(return_value={"result": "CRISIS!!!"})

    monkeypatch.setattr(orch, "_crisis_chain", mock_crisis_chain)
    # CRUCIAL FIX: Re-initialize orch.chain to use the mocked _crisis_chain
    orch.chain = BranchingChain(orch._detect_risk, orch._crisis_chain, orch._rag_chain)

    assert await orch.answer("I want to die") == "CRISIS!!!"


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch):
    orch = Orchestrator()

    mock_branching_chain = AsyncMock()
    mock_branching_chain.ainvoke.side_effect = RuntimeError("Simulated chain error")

    monkeypatch.setattr(orch, "chain", mock_branching_chain)
    assert await orch.answer("anything") == "I’m sorry, I’m unable to answer that right now. Please try again later."


@pytest.mark.asyncio
async def test_summarize_session_success(monkeypatch):
    orch = RagOrchestrator()
    mock_summarize_chain = AsyncMock()
    mock_summarize_chain.ainvoke = AsyncMock(return_value={"output_text": "SESSION SUMMARY"})

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
def create_mock_settings(lang: str, **kwargs) -> Settings:
    # Provide default values for all required fields in Settings
    # to avoid validation errors when instantiating.
    # Adjust these defaults if your Settings model changes.
    defaults = {
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
        "OPENAI_API_KEY": "test_api_key",
        "LLM_MODEL": "gpt-4o",
        "LLM_TEMPERATURE": 0.7,
        "DEMO_USER_EMAIL": "demo@example.com",
        "DEMO_USER_PASSWORD": "password",
        "APP_DEFAULT_LANGUAGE": lang,
    }
    defaults.update(kwargs)
    return Settings(**defaults)


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
    monkeypatch,
    lang_setting,
    he_files_exist,
    en_files_exist,
    expected_crisis_content,
    expected_system_content,
    expect_warning,
):
    # 1. Mock get_settings
    mock_settings = create_mock_settings(lang=lang_setting)
    monkeypatch.setattr("app.api.orchestrator.get_settings", lambda: mock_settings)

    # 2. Mock os.path.exists
    def mock_path_exists(path):
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
    file_contents = {}
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
    def open_side_effect(path, *args, **kwargs):
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
    actual_prompt_contents_passed = []
    original_from_template = ChatPromptTemplate.from_template

    def mock_from_template_capture(template_content_str, **kwargs):
        actual_prompt_contents_passed.append(template_content_str)
        # Return a ChatPromptTemplate that includes expected variables
        # to satisfy internal chain validations.
        # The crisis chain prompt uses {context} and {query}
        # The RAG chain prompt uses {context} and {input}
        if "crisis_prompt" in template_content_str.lower() or (
            expected_crisis_content and expected_crisis_content.lower() in template_content_str.lower()
        ):
            # print(f"DEBUG: Creating crisis-like mock prompt for: {template_content_str[:50]}")
            return original_from_template(template="dummy crisis {context} {query}", **kwargs)
        # print(f"DEBUG: Creating RAG-like mock prompt for: {template_content_str[:50]}")
        return original_from_template(template="dummy rag {context} {input}", **kwargs)

    monkeypatch.setattr(ChatPromptTemplate, "from_template", mock_from_template_capture)

    # 5. Mock logging.warning
    mock_log_warning = MagicMock()
    monkeypatch.setattr(logging, "warning", mock_log_warning)  # Patch logging at module level used by orchestrator

    # 6. Mock DocumentProcessor to avoid its __init__ side effects (ChromaDB, embeddings)
    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    # Configure the 'vectordb' attribute on the mock_dp_instance itself
    # to be another MagicMock.
    mock_vectordb = MagicMock()

    # The object returned by as_retriever() needs to be acceptable to CombinedRetriever.
    # We can make it a MagicMock that also acts like a BaseRetriever.
    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)  # spec_set is stricter
    mock_retriever_instance.get_relevant_documents = MagicMock(
        return_value=[]
    )  # Implement required abstract methods if any, or ensure spec handles it
    mock_retriever_instance.aget_relevant_documents = AsyncMock(return_value=[])
    mock_vectordb.as_retriever.return_value = mock_retriever_instance
    mock_dp_instance.vectordb = mock_vectordb
    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda ns: mock_dp_instance)

    # 7. Instantiate Orchestrator - this will trigger the prompt loading
    Orchestrator()

    # 8. Assertions
    # Check that from_template was called with the expected content
    # It will be called twice (once for crisis, once for system)
    assert (
        len(actual_prompt_contents_passed) >= 2
    ), f"ChatPromptTemplate.from_template not called enough times. Called {len(actual_prompt_contents_passed)} times. Content: {actual_prompt_contents_passed}"

    # Check if the expected crisis content was passed to from_template
    assert any(
        expected_crisis_content in content for content in actual_prompt_contents_passed
    ), f"Expected crisis content '{expected_crisis_content}' not found in {actual_prompt_contents_passed}"

    # Check if the expected system content was passed to from_template
    assert any(
        expected_system_content in content for content in actual_prompt_contents_passed
    ), f"Expected system content '{expected_system_content}' not found in {actual_prompt_contents_passed}"

    if expect_warning:
        assert mock_log_warning.called, "Expected logging.warning to be called for fallback"
        # More specific checks on warning messages can be added if needed
        # e.g., any("Falling back to English" in call_args[0][0] for call_args in mock_log_warning.call_args_list)
    else:
        # Check that no unexpected fallback warnings occurred for non-fallback cases
        unexpected_fallback_logged = False
        for call_args in mock_log_warning.call_args_list:
            if "Falling back to English" in call_args[0][0]:  # Check the first arg of the call
                unexpected_fallback_logged = True
                break
        assert not unexpected_fallback_logged, f"Unexpected fallback warning logged: {mock_log_warning.call_args_list}"
