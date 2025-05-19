# /home/dfront/code/dear_future_me/tests/test_orchestrator.py
import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from conftest import create_mock_settings
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.orchestrator import RagOrchestrator
from app.auth.models import SafetyPlanTable, UserProfileTable, UserTable
from app.rag.processor import DocumentProcessor


@pytest.fixture(autouse=True)
def mock_orchestrator_cfg_for_tests(monkeypatch: pytest.MonkeyPatch):
    default_mock_settings_for_module = create_mock_settings()
    monkeypatch.setattr("app.api.orchestrator.cfg", default_mock_settings_for_module)
    monkeypatch.setattr("app.rag.processor.cfg", default_mock_settings_for_module)
    # Also patch app.core.settings.get_settings if mock_open_side_effect needs it
    # or ensure app_core_settings_module.cfg is correctly set if that's the intended pattern.
    # For now, let's assume app.api.orchestrator.cfg is the primary one used by _load_prompts indirectly.
    # The test's mock_open_side_effect will use get_settings() from app.core.settings.


@pytest.fixture
def mock_llm_and_chains(monkeypatch: pytest.MonkeyPatch):
    mock_llm_instance = AsyncMock(spec=ChatOpenAI)
    mock_llm_instance.ainvoke = AsyncMock()
    monkeypatch.setattr("app.api.orchestrator.ChatOpenAI", lambda **kwargs: mock_llm_instance)

    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_vectordb = MagicMock()  # This will be the mock for the Chroma instance
    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)
    mock_retriever_instance.ainvoke = AsyncMock(return_value=[Document(page_content="Retrieved content")])

    # Configure as_retriever on mock_vectordb
    mock_vectordb.as_retriever = MagicMock(return_value=mock_retriever_instance)

    # Assign mock_vectordb to the vectordb attribute of mock_dp_instance
    mock_dp_instance.vectordb = mock_vectordb  # CRITICAL FIX HERE

    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda namespace: mock_dp_instance)

    return mock_llm_instance, mock_dp_instance


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch, mock_llm_and_chains):
    orch = RagOrchestrator()

    mock_chain_itself = AsyncMock(spec=Runnable)
    mock_chain_itself.ainvoke = AsyncMock(side_effect=RuntimeError("Simulated chain error"))

    monkeypatch.setattr(orch, "summarize_chain", mock_chain_itself)
    assert await orch.summarize_session("sessX") == "Summary for {session_id} (unavailable due to error)".format(
        session_id="sessX"
    )


def test_rag_orchestrator_has_future_db(mock_llm_and_chains):
    orch = RagOrchestrator()
    assert hasattr(orch, "future_me_db"), "RagOrchestrator must have future_me_db"
    # Add a check to ensure future_me_db.vectordb.as_retriever is callable if possible,
    # or that future_me_db.vectordb is the mock_vectordb we expect.
    assert isinstance(orch.future_me_db.vectordb.as_retriever, MagicMock)


@pytest.mark.asyncio
async def test_orchestrator_includes_user_data_in_prompt(
    monkeypatch: pytest.MonkeyPatch, mock_llm_and_chains: Any, db_session: AsyncSession
):
    user_id = uuid.uuid4()
    mock_user = UserTable(
        id=user_id,
        email="testuser@example.com",
        is_active=True,
        is_verified=True,
        is_superuser=False,
        hashed_password="fake",
    )

    mock_profile_data = UserProfileTable(
        user_id=user_id,
        name="Test User",
        future_me_persona_summary="A resilient and kind individual.",
        gender_identity_pronouns="they/them",
        therapeutic_setting="online chat",
    )
    mock_safety_plan_data = SafetyPlanTable(
        user_id=user_id,
        warning_signs="Feeling overwhelmed",
        coping_strategies="Deep breathing exercises",
    )

    mock_get_user_profile = AsyncMock(return_value=mock_profile_data)
    mock_get_safety_plan = AsyncMock(return_value=mock_safety_plan_data)

    monkeypatch.setattr("app.api.orchestrator.crud_profile.get_user_profile", mock_get_user_profile)
    monkeypatch.setattr("app.api.orchestrator.safety_plan_crud.get_safety_plan_by_user_id", mock_get_safety_plan)

    @asynccontextmanager
    async def mock_get_session_context():
        yield db_session

    monkeypatch.setattr("app.api.orchestrator.get_async_session_context", mock_get_session_context)

    test_system_prompt_str = (
        "System Context: {context}\nUser Input: {input}\n"
        "--- User Data ---\n"
        "Name: {user_name}\n"
        "Profile Summary: {user_profile_summary}\n"
        "Future Persona: {future_me_persona_summary}\n"
        "Pronouns: {gender_identity_pronouns}\n"
        "Setting: {therapeutic_setting}\n"
        "Safety Plan: {user_safety_plan_summary}\n"
        "Values: {identified_values}\n"
        "Tone: {tone_alignment}\n"
        "Goals: {self_reported_goals}\n"
        "Triggers: {recent_triggers_events}\n"
        "Strengths: {emotion_regulation_strengths}\n"
        "Themes: {primary_emotional_themes}\n"
        "Mirror: {therapist_language_to_mirror}\n"
        "Preference: {user_emotional_tone_preference}"
    )
    test_crisis_prompt_str = "CRISIS: {query} for user {user_name}."

    original_open = open

    # Use get_settings() to access the (potentially mocked) settings instance
    # This settings_for_test will be the one patched by mock_orchestrator_cfg_for_tests
    # if that fixture correctly patches the source used by get_settings() or app.api.orchestrator.cfg
    # The mock_orchestrator_cfg_for_tests fixture patches app.api.orchestrator.cfg.
    # The _load_prompts method in Orchestrator uses self.settings which is app.api.orchestrator.cfg.

    # To ensure mock_open_side_effect uses the correct settings for file names:
    # We rely on the fact that mock_orchestrator_cfg_for_tests has already patched
    # app.api.orchestrator.cfg. The Orchestrator instance will use this patched cfg.
    # So, self.settings.SYSTEM_PROMPT_FILE inside _load_prompts will be the test value.

    def mock_open_side_effect(file_path, *args, **kwargs):
        # Access the settings instance that the Orchestrator will use.
        # This is tricky because it's a module-level global in orchestrator.py
        # that's patched by a fixture.
        # A cleaner way: Orchestrator could take settings in __init__.
        # For now, assume the patch on app.api.orchestrator.cfg is effective.
        # We'll compare file_path with the expected filenames.

        # Get the current settings that the orchestrator would be using
        # This relies on mock_orchestrator_cfg_for_tests correctly patching
        # the cfg instance that Orchestrator's _load_prompts will see.
        # Let's assume Orchestrator uses self.settings which is cfg from its module.
        # The test settings are set by create_mock_settings()

        # We need to know what file names _load_prompts will try to open.
        # These come from self.settings.SYSTEM_PROMPT_FILE and self.settings.CRISIS_PROMPT_FILE
        # within the Orchestrator instance.
        # The mock_orchestrator_cfg_for_tests fixture sets app.api.orchestrator.cfg.
        # So, when RagOrchestrator is initialized, self.settings will be this mocked cfg.

        # To make this robust, we should ideally get these filenames from the
        # same source the orchestrator uses.
        # For this test, we'll assume the default filenames from create_mock_settings if not overridden.
        # The create_mock_settings sets these:
        # mock_settings.CRISIS_PROMPT_FILE = "crisis_prompt.md"
        # mock_settings.SYSTEM_PROMPT_FILE = "system_prompt.md"

        # Let's use the values from the mocked settings directly for comparison
        # This requires that mock_orchestrator_cfg_for_tests has run and patched app.api.orchestrator.cfg
        # We can access this patched cfg via app.api.orchestrator.cfg if needed, but it's cleaner
        # to rely on the file names being consistent.

        # The orchestrator instance will use its self.settings.
        # We are mocking 'open' before the orchestrator is initialized.
        # So, we need to anticipate the filenames.
        # The mock_orchestrator_cfg_for_tests fixture ensures that
        # app.api.orchestrator.cfg has specific values for these filenames.

        # Let's use the values that create_mock_settings() defines, as these
        # will be on the cfg object used by the Orchestrator instance.
        # This is a bit of a roundabout way to get the settings that _load_prompts will use.
        # A more direct way would be to mock _load_prompts itself.

        # Simplification: Assume the filenames are known or use the default from create_mock_settings
        # The orchestrator instance will have its self.settings set by the fixture.
        # When self.settings.SYSTEM_PROMPT_FILE is accessed in _load_prompts, it will be the mocked value.

        # The key is that when _load_prompts constructs the path, e.g.,
        # os.path.join(template_dir, self.settings.SYSTEM_PROMPT_FILE),
        # self.settings.SYSTEM_PROMPT_FILE will be "system_prompt.md" (from create_mock_settings).

        if "system_prompt.md" in str(file_path):  # Assuming default filename from create_mock_settings
            return mock_open(read_data=test_system_prompt_str)()
        elif "crisis_prompt.md" in str(file_path):  # Assuming default filename
            return mock_open(read_data=test_crisis_prompt_str)()
        return original_open(file_path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open_side_effect)
    monkeypatch.setattr("app.api.orchestrator.os.path.exists", MagicMock(return_value=True))

    llm_call_args_list = []
    mock_llm_instance = mock_llm_and_chains[0]

    with patch.object(mock_llm_instance, "ainvoke") as patched_ainvoke:

        async def side_effect_for_ainvoke(prompt_input_arg, *args, **kwargs):
            llm_call_args_list.append(prompt_input_arg)
            return AIMessage(content="Mocked LLM Output via patch.object")

        patched_ainvoke.side_effect = side_effect_for_ainvoke

        orchestrator = RagOrchestrator()

        await orchestrator.answer("Hello, how are you?", user=mock_user)

    mock_get_user_profile.assert_called_once_with(db_session, user_id=user_id)
    mock_get_safety_plan.assert_called_once_with(db_session, user_id=user_id)

    assert patched_ainvoke.call_count > 0, "LLM ainvoke (patched) was not called"
    assert len(llm_call_args_list) > 0, "LLM call arguments were not captured by side_effect"

    final_prompt_to_llm = llm_call_args_list[-1]

    prompt_string_content = ""
    if hasattr(final_prompt_to_llm, "to_string"):
        prompt_string_content = final_prompt_to_llm.to_string()
    elif hasattr(final_prompt_to_llm, "messages"):
        prompt_string_content = " ".join(
            [msg.content for msg in final_prompt_to_llm.messages if hasattr(msg, "content")]
        )
    elif isinstance(final_prompt_to_llm, str):
        prompt_string_content = final_prompt_to_llm
    else:
        prompt_string_content = str(final_prompt_to_llm)

    assert "Name: Test User" in prompt_string_content
    assert (
        "Profile Summary: Name: Test User. Persona Summary: A resilient and kind individual." in prompt_string_content
    )
    assert "Future Persona: A resilient and kind individual." in prompt_string_content
    assert "Pronouns: they/them" in prompt_string_content
    assert "Setting: online chat" in prompt_string_content
    assert (
        "Safety Plan: Warning Signs: Feeling overwhelmed. Coping Strategies: Deep breathing exercises."
        in prompt_string_content
    )

    assert "Values: Values not specified" in prompt_string_content
    assert "Tone: Tone alignment not specified" in prompt_string_content
