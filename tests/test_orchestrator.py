# /home/dfront/code/dear_future_me/tests/test_orchestrator.py
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import create_mock_settings  # Use absolute import from conftest
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable

from app.api.orchestrator import RagOrchestrator
from app.rag.processor import DocumentProcessor


@pytest.fixture(autouse=True)
def mock_orchestrator_cfg_for_tests(monkeypatch: pytest.MonkeyPatch):
    """Mocks cfg for the orchestrator and processor modules for consistency in these tests."""
    default_mock_settings_for_module = create_mock_settings()  # Removed lang parameter
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
async def test_summarize_session_fallback(monkeypatch, mock_llm_and_chains):
    orch = RagOrchestrator()
    mock_chain_itself = AsyncMock(spec=Runnable)
    mock_chain_itself.ainvoke.side_effect = RuntimeError("Simulated chain error")
    monkeypatch.setattr(orch, "summarize_chain", mock_chain_itself)
    assert await orch.summarize_session("sessX") == "Summary for sessX (unavailable due to error)"


def test_rag_orchestrator_has_future_db(mock_llm_and_chains):
    orch = RagOrchestrator()
    assert hasattr(orch, "future_me_db"), "RagOrchestrator must have future_me_db"


# Removed the test_orchestrator_prompt_loading_by_language test
# as it specifically tested language-specific prompt loading logic which is being removed.
# If you need to test generic prompt loading, a new, simpler test would be required.

# Example of a simpler test if needed (not included in the diff):
# def test_orchestrator_loads_default_prompts(monkeypatch, mock_llm_and_chains):
#     # Mock os.path.exists and open to simulate default files existing
#     mock_path_exists = MagicMock(return_value=True)
#     mock_open_obj = mock_open(read_data="Default Crisis Prompt")
#     mock_open_obj.side_effect = lambda path, *args, **kwargs: mock_open(read_data="Default Crisis Prompt" if "crisis" in path else "Default System Prompt")(*args, **kwargs)
#     monkeypatch.setattr("app.api.orchestrator.os.path.exists", mock_path_exists)
#     monkeypatch.setattr("builtins.open", mock_open_obj)
#
#     # Mock ChatPromptTemplate.from_template to capture input
#     actual_prompt_contents_passed = []
#     original_from_template = ChatPromptTemplate.from_template
#     def mock_from_template_capture(template_content_str, **kwargs):
#         actual_prompt_contents_passed.append(template_content_str)
#         # Return a dummy template that won't fail validation
#         return original_from_template(template="{query} {context} {user_profile_summary} {user_safety_plan_summary}")
#     monkeypatch.setattr(ChatPromptTemplate, "from_template", mock_from_template_capture)
#
#     Orchestrator()
#
#     assert len(actual_prompt_contents_passed) >= 2
#     assert "Default Crisis Prompt" in actual_prompt_contents_passed
#     assert "Default System Prompt" in actual_prompt_contents_passed
