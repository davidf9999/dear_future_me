# tests/test_orchestrator.py
# Full file content
import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
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
def mock_orchestrator_cfg_for_tests(monkeypatch: MonkeyPatch):
    default_mock_settings_for_module = create_mock_settings()
    monkeypatch.setattr("app.api.orchestrator.cfg", default_mock_settings_for_module)
    monkeypatch.setattr("app.rag.processor.cfg", default_mock_settings_for_module)


@pytest.fixture
def mock_llm_and_chains(monkeypatch: MonkeyPatch):
    mock_llm_instance = AsyncMock(spec=ChatOpenAI)
    mock_llm_instance.ainvoke = AsyncMock()
    monkeypatch.setattr("app.api.orchestrator.ChatOpenAI", lambda **kwargs: mock_llm_instance)

    mock_dp_instance = MagicMock(spec=DocumentProcessor)
    mock_vectordb = MagicMock()
    mock_retriever_instance = MagicMock(spec_set=BaseRetriever)
    mock_retriever_instance.ainvoke = AsyncMock(return_value=[Document(page_content="Retrieved content")])

    mock_vectordb.as_retriever = MagicMock(return_value=mock_retriever_instance)
    mock_dp_instance.vectordb = mock_vectordb

    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", lambda namespace: mock_dp_instance)

    return mock_llm_instance, mock_dp_instance


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch: MonkeyPatch, mock_llm_and_chains):
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
    assert isinstance(orch.future_me_db.vectordb.as_retriever, MagicMock)


@pytest.mark.asyncio
async def test_orchestrator_includes_user_data_in_prompt(
    monkeypatch: MonkeyPatch, mock_llm_and_chains: Any, db_session: AsyncSession
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
        emotion_regulation_strengths="Journaling, mindful breathing",  # Provide value for strengths
    )
    mock_safety_plan_data = SafetyPlanTable(
        user_id=user_id,
        step_1_warning_signs="Feeling overwhelmed",
        step_2_internal_coping="Deep breathing exercises",
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
        "Safety Plan Summary: {user_safety_plan_summary}\n"
        "Values: {identified_values}\n"
        "Tone: {tone_alignment}\n"
        "Goals: {self_reported_goals}\n"
        "Triggers: {recent_triggers_events}\n"
        "Emotion Regulation Strengths: {emotion_regulation_strengths}\n"  # System prompt uses this
        "User Strengths: {user_strengths}\n"  # System prompt might also use this if crisis doesn't
        "Themes: {primary_emotional_themes}\n"
        "Mirror: {therapist_language_to_mirror}\n"
        "Preference: {user_emotional_tone_preference}"
    )
    # Crisis prompt expects user_strengths
    test_crisis_prompt_str = "CRISIS: {query} for user {user_name}. Pronouns: {user_pronouns}. Strengths: {user_strengths}. Safety Context: {context}"

    original_open = open

    def mock_open_side_effect(file_path, *args, **kwargs):
        if "system_prompt.md" in str(file_path):
            return mock_open(read_data=test_system_prompt_str)()
        elif "crisis_prompt.md" in str(file_path):
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
        # This call will use the RAG chain, which uses system_prompt.md
        await orchestrator.answer("Hello, how are you?", user=mock_user)

    mock_get_user_profile.assert_called_once_with(db_session, user_id=user_id)
    mock_get_safety_plan.assert_called_once_with(db_session, user_id=user_id)

    assert patched_ainvoke.call_count > 0, "LLM ainvoke (patched) was not called"
    assert len(llm_call_args_list) > 0, "LLM call arguments were not captured by side_effect"

    final_prompt_to_llm = llm_call_args_list[-1]  # This will be the system prompt

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
    assert "Emotion Regulation Strengths: Journaling, mindful breathing" in prompt_string_content
    assert (
        "User Strengths: Journaling, mindful breathing" in prompt_string_content
    )  # Check if it's passed to system prompt too
    assert (
        "Safety Plan Summary: Warning Signs: Feeling overwhelmed. Internal Coping Strategies: Deep breathing exercises."
    ) in prompt_string_content


@pytest.mark.asyncio
async def test_orchestrator_crisis_prompt_includes_safety_plan_context_and_strengths(
    monkeypatch: MonkeyPatch, mock_llm_and_chains: Any, db_session: AsyncSession
):
    user_id = uuid.uuid4()
    mock_user = UserTable(
        id=user_id,
        email="crisisuser@example.com",
        hashed_password="fake",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    mock_profile_data = UserProfileTable(
        user_id=user_id,
        name="Crisis User",
        gender_identity_pronouns="they/them",
        emotion_regulation_strengths="Resilience, Reaching out",  # Provide strengths
    )
    mock_safety_plan_data = SafetyPlanTable(
        user_id=user_id,
        step_1_warning_signs="Feeling very down",
        step_2_internal_coping="Listen to music",
        step_3_social_distractions="Call Sam",
        step_4_help_sources="Therapist Dr. X",
        step_5_professional_resources="Hotline Y",
        step_6_environment_risk_reduction="Remove Z",
    )

    monkeypatch.setattr("app.api.orchestrator.crud_profile.get_user_profile", AsyncMock(return_value=mock_profile_data))
    monkeypatch.setattr(
        "app.api.orchestrator.safety_plan_crud.get_safety_plan_by_user_id",
        AsyncMock(return_value=mock_safety_plan_data),
    )

    @asynccontextmanager
    async def mock_get_session_context():
        yield db_session

    monkeypatch.setattr("app.api.orchestrator.get_async_session_context", mock_get_session_context)

    # Ensure crisis_prompt.md is "loaded" by mock_open and expects user_strengths
    test_crisis_prompt_str_for_this_test = "CRISIS: {query} for user {user_name}. Pronouns: {user_pronouns}. Strengths: {user_strengths}. Safety Context: {context}"
    original_open = open

    def mock_open_crisis_test(file_path, *args, **kwargs):
        if "crisis_prompt.md" in str(file_path):  # Make sure it loads the crisis prompt
            return mock_open(read_data=test_crisis_prompt_str_for_this_test)()
        # Allow system_prompt.md to be loaded as well if Orchestrator init needs it
        elif "system_prompt.md" in str(file_path):
            return mock_open(
                read_data="System prompt content {input} {context} {user_name} {user_pronouns} {emotion_regulation_strengths} {user_strengths} {user_profile_summary} {future_me_persona_summary} {gender_identity_pronouns} {therapeutic_setting} {user_safety_plan_summary} {identified_values} {tone_alignment} {self_reported_goals} {recent_triggers_events} {primary_emotional_themes} {therapist_language_to_mirror} {user_emotional_tone_preference}"
            )()
        return original_open(file_path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", mock_open_crisis_test)
    monkeypatch.setattr("app.api.orchestrator.os.path.exists", MagicMock(return_value=True))

    llm_call_args_list = []
    mock_llm_instance = mock_llm_and_chains[0]

    with patch.object(mock_llm_instance, "ainvoke") as patched_ainvoke:

        async def side_effect_for_ainvoke(prompt_input_arg, *args, **kwargs):
            llm_call_args_list.append(prompt_input_arg)
            return AIMessage(content="Mocked Crisis LLM Output")

        patched_ainvoke.side_effect = side_effect_for_ainvoke

        orchestrator = RagOrchestrator()
        await orchestrator.answer("I want to die", user=mock_user)  # Triggers crisis path

    assert patched_ainvoke.call_count > 0, "LLM ainvoke (patched) was not called for crisis"
    assert len(llm_call_args_list) > 0, "LLM call arguments were not captured for crisis"

    crisis_prompt_to_llm = llm_call_args_list[0]
    prompt_string_content = crisis_prompt_to_llm.to_string()

    assert (
        "User Profile: Name: Crisis User" not in prompt_string_content
    )  # Default crisis prompt doesn't have "User Profile:" prefix
    assert "user Crisis User" in prompt_string_content  # Check for user name
    assert "Pronouns: they/them" in prompt_string_content
    assert "Strengths: Resilience, Reaching out" in prompt_string_content  # Check for strengths
    assert "Safety Context:" in prompt_string_content
    assert "- Warning Signs: Feeling very down" in prompt_string_content
    assert "- Internal Coping Strategies: Listen to music" in prompt_string_content
