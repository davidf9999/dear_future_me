# /home/dfront/code/dear_future_me/tests/test_orchestrator.py
import os
from typing import Any, Dict, List, Literal
from unittest.mock import AsyncMock, MagicMock, mock_open

import pytest
from conftest import create_mock_settings
from langchain.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable

from app.api.orchestrator import Orchestrator, RagOrchestrator

# Import the actual settings module to get its file path for absolute path construction
from app.core import settings as app_core_settings_module
from app.rag.processor import DocumentProcessor


@pytest.fixture(autouse=True)
def mock_orchestrator_cfg_for_tests(monkeypatch: pytest.MonkeyPatch):
    """Mocks cfg for the orchestrator and processor modules for consistency in these tests."""
    # This fixture will be active for all tests in this file.
    # Tests requiring different settings variations (like prompt loading) will override further.
    default_mock_settings_for_module = create_mock_settings()
    monkeypatch.setattr("app.api.orchestrator.cfg", default_mock_settings_for_module)
    monkeypatch.setattr("app.rag.processor.cfg", default_mock_settings_for_module)


@pytest.fixture
def mock_llm_and_chains(monkeypatch: pytest.MonkeyPatch):
    """Mocks LLM and DocumentProcessor for Orchestrator/RagOrchestrator tests."""
    mock_llm_instance = AsyncMock()
    mock_llm_instance.ainvoke = AsyncMock(return_value="Mocked LLM Output")
    monkeypatch.setattr("app.api.orchestrator.ChatOpenAI", lambda **kwargs: mock_llm_instance)

    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_vectordb = MagicMock()
    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)
    mock_retriever_instance.ainvoke = AsyncMock(return_value=[Document(page_content="Retrieved content")])
    mock_vectordb.as_retriever.return_value = mock_retriever_instance
    mock_dp_instance.vectordb = mock_vectordb
    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda namespace: mock_dp_instance)
    return mock_llm_instance, mock_dp_instance


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch, mock_llm_and_chains):  # Uses mocked LLM
    orch = RagOrchestrator()
    mock_chain_itself = AsyncMock(spec=Runnable)
    mock_chain_itself.ainvoke.side_effect = RuntimeError("Simulated chain error")
    monkeypatch.setattr(orch, "summarize_chain", mock_chain_itself)
    assert await orch.summarize_session("sessX") == "Summary for sessX (unavailable due to error)"


def test_rag_orchestrator_has_future_db(mock_llm_and_chains):  # Uses mocked DocumentProcessor
    orch = RagOrchestrator()
    assert hasattr(orch, "future_me_db"), "RagOrchestrator must have future_me_db"


@pytest.mark.parametrize(
    "lang_setting, he_files_exist, en_files_exist, expected_crisis_content, expected_system_content, expect_warning",
    [
        ("he", True, True, "Hebrew Crisis Prompt", "Hebrew System Prompt", False),
        ("he", False, True, "English Crisis Prompt", "English System Prompt", True),
        ("en", False, True, "English Crisis Prompt", "English System Prompt", False),
        ("he", False, False, "You are a crisis responder.", "Based on the following context:", True),
        (
            "en",
            False,
            False,
            "You are a crisis responder.",
            "Based on the following context:",
            True,
        ),
    ],
)
def test_orchestrator_prompt_loading_by_language(
    monkeypatch: pytest.MonkeyPatch,
    lang_setting: Literal["en", "he"],
    he_files_exist: bool,
    en_files_exist: bool,
    expected_crisis_content: str,
    expected_system_content: str,
    expect_warning: bool,
    mock_llm_and_chains,  # Ensures DocumentProcessor is mocked for Orchestrator init
):
    specific_test_settings = create_mock_settings(lang=lang_setting)
    monkeypatch.setattr("app.api.orchestrator.cfg", specific_test_settings)

    # Determine the project root based on the location of the settings module
    # This helps construct absolute paths similar to how Orchestrator does.
    project_root_for_test = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(app_core_settings_module.__file__)))
    )

    def mock_path_exists(path: str) -> bool:
        # Orchestrator constructs absolute paths. The mock needs to check for these.
        # Example path from orchestrator: PROJECT_ROOT/templates/crisis_prompt.he.md

        # Normalize the incoming path for consistent comparison
        normalized_path = os.path.normpath(path)

        # Paths expected by the mock based on test parameters
        # These are relative to PROJECT_ROOT/templates
        rel_crisis_file_lang = os.path.join(
            specific_test_settings.PROMPT_TEMPLATE_DIR,
            f"{specific_test_settings.CRISIS_PROMPT_FILE.split('.')[0]}.{lang_setting}.md",
        )
        rel_system_file_lang = os.path.join(
            specific_test_settings.PROMPT_TEMPLATE_DIR,
            f"{specific_test_settings.SYSTEM_PROMPT_FILE.split('.')[0]}.{lang_setting}.md",
        )
        rel_crisis_file_generic = os.path.join(
            specific_test_settings.PROMPT_TEMPLATE_DIR, specific_test_settings.CRISIS_PROMPT_FILE
        )
        rel_system_file_generic = os.path.join(
            specific_test_settings.PROMPT_TEMPLATE_DIR, specific_test_settings.SYSTEM_PROMPT_FILE
        )

        abs_path_map = {
            os.path.normpath(os.path.join(project_root_for_test, rel_crisis_file_lang)): he_files_exist
            if lang_setting == "he"
            else en_files_exist,
            os.path.normpath(os.path.join(project_root_for_test, rel_system_file_lang)): he_files_exist
            if lang_setting == "he"
            else en_files_exist,
            os.path.normpath(os.path.join(project_root_for_test, rel_crisis_file_generic)): en_files_exist,
            os.path.normpath(os.path.join(project_root_for_test, rel_system_file_generic)): en_files_exist,
        }
        if lang_setting == "en":  # Specific .en.md files
            abs_path_map[os.path.normpath(os.path.join(project_root_for_test, rel_crisis_file_lang))] = en_files_exist
            abs_path_map[os.path.normpath(os.path.join(project_root_for_test, rel_system_file_lang))] = en_files_exist

        # print(f"DEBUG mock_path_exists: Checking '{normalized_path}'. Match found: {abs_path_map.get(normalized_path, False)}")
        return abs_path_map.get(normalized_path, False)

    monkeypatch.setattr("app.api.orchestrator.os.path.exists", mock_path_exists)

    file_contents_map_abs: Dict[str, str] = {}  # Store absolute paths
    if he_files_exist:
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "crisis_prompt.he.md")
        )
        file_contents_map_abs[abs_path] = "Hebrew Crisis Prompt"
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "system_prompt.he.md")
        )
        file_contents_map_abs[abs_path] = "Hebrew System Prompt"
    if en_files_exist:
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "crisis_prompt.md")
        )
        file_contents_map_abs[abs_path] = "English Crisis Prompt"
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "system_prompt.md")
        )
        file_contents_map_abs[abs_path] = "English System Prompt"
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "crisis_prompt.en.md")
        )
        file_contents_map_abs[abs_path] = "English Crisis Prompt"  # Assuming same content for .en.md
        abs_path = os.path.normpath(
            os.path.join(project_root_for_test, specific_test_settings.PROMPT_TEMPLATE_DIR, "system_prompt.en.md")
        )
        file_contents_map_abs[abs_path] = "English System Prompt"  # Assuming same content for .en.md

    def open_side_effect(path: str, *args: Any, **kwargs: Any) -> Any:
        normalized_path = os.path.normpath(path)
        # print(f"DEBUG open_side_effect: Trying to open '{normalized_path}'. Available in mock: {normalized_path in file_contents_map_abs}")
        if normalized_path in file_contents_map_abs:
            return mock_open(read_data=file_contents_map_abs[normalized_path])(*args, **kwargs)

        # This condition for raising FileNotFoundError for defaults might be too broad
        # if (not he_files_exist and not en_files_exist) and \
        #    any(prompt_part in normalized_path for prompt_part in ["crisis_prompt", "system_prompt"]):
        #     raise FileNotFoundError(f"Mocked FileNotFoundError for default trigger {normalized_path}")

        raise FileNotFoundError(f"Mocked FileNotFoundError for unhandled path: {normalized_path}")

    monkeypatch.setattr("builtins.open", open_side_effect)

    actual_prompt_contents_passed: List[str] = []
    original_from_template = ChatPromptTemplate.from_template

    def mock_from_template_capture(template_content_str: str, **kwargs: Any) -> ChatPromptTemplate:
        actual_prompt_contents_passed.append(template_content_str)
        if "crisis responder" in template_content_str.lower() or (
            expected_crisis_content and expected_crisis_content.lower() in template_content_str.lower()
        ):
            return original_from_template(
                template="{query} {context} {user_profile_summary} {user_safety_plan_summary}", **kwargs
            )
        else:
            return original_from_template(
                template="{input} {context} {user_profile_summary} {user_safety_plan_summary}", **kwargs
            )

    monkeypatch.setattr(ChatPromptTemplate, "from_template", mock_from_template_capture)

    mock_log_warning = MagicMock()
    monkeypatch.setattr("app.api.orchestrator.logging.warning", mock_log_warning)

    Orchestrator()

    # print(f"DEBUG: Actual prompts passed to template: {actual_prompt_contents_passed}")

    assert len(actual_prompt_contents_passed) >= 2, (
        f"Expected at least 2 prompts. Got: {len(actual_prompt_contents_passed)}, Content: {actual_prompt_contents_passed}"
    )

    assert any(expected_crisis_content in content for content in actual_prompt_contents_passed), (
        f"Expected crisis content '{expected_crisis_content}' not found in {actual_prompt_contents_passed}"
    )

    assert any(expected_system_content in content for content in actual_prompt_contents_passed), (
        f"Expected system content '{expected_system_content}' not found in {actual_prompt_contents_passed}"
    )

    if expect_warning:
        mock_log_warning.assert_called()
    else:
        mock_log_warning.assert_not_called()
