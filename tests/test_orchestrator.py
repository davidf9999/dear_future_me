# /home/dfront/code/dear_future_me/tests/test_orchestrator.py
# Full file content
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, mock_open, patch  # Import ANY

import pytest
from _pytest.monkeypatch import MonkeyPatch
from conftest import create_mock_settings
from langchain.retrievers import EnsembleRetriever  # Added import
from langchain_core.documents import Document
from langchain_core.messages import AIMessage
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.orchestrator import RagOrchestrator
from app.auth.models import SafetyPlanTable, UserProfileTable, UserTable
from app.rag.processor import DocumentProcessor

# Removed: from app.api.orchestrator import cfg as orchestrator_cfg_module
# We will import cfg inside functions to ensure we get the patched version.


@pytest.fixture(autouse=True)
def mock_orchestrator_cfg_for_tests(monkeypatch: MonkeyPatch):
    # Uses create_mock_settings from conftest.py which defines test namespaces
    default_mock_settings_for_module = create_mock_settings()
    monkeypatch.setattr("app.api.orchestrator.cfg", default_mock_settings_for_module)
    monkeypatch.setattr("app.rag.processor.cfg", default_mock_settings_for_module)
    # This ensures that when app.api.orchestrator.cfg is imported or used,
    # it gets this mocked version.


@pytest.fixture
def mock_llm_and_chains(monkeypatch: MonkeyPatch, mock_orchestrator_cfg_for_tests: Any):
    # mock_orchestrator_cfg_for_tests fixture ensures cfg is patched before this runs
    # Access the cfg that has been patched by mock_orchestrator_cfg_for_tests
    from app.api.orchestrator import (
        cfg as patched_orchestrator_cfg,  # Import here to get patched version
    )

    cfg = patched_orchestrator_cfg

    mock_llm_instance = AsyncMock(spec=ChatOpenAI)
    mock_llm_instance.ainvoke = AsyncMock()  # Default mock for LLM
    monkeypatch.setattr("app.api.orchestrator.ChatOpenAI", lambda **kwargs: mock_llm_instance)

    mock_document_processors_retrievers = {}

    namespaces_to_mock = [
        cfg.CHROMA_NAMESPACE_THEORY,
        cfg.CHROMA_NAMESPACE_PERSONAL_PLAN,
        cfg.CHROMA_NAMESPACE_SESSION_DATA,
        cfg.CHROMA_NAMESPACE_FUTURE_ME,
        cfg.CHROMA_NAMESPACE_THERAPIST_NOTES,
        cfg.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES,
    ]

    for ns in namespaces_to_mock:
        retriever_mock = AsyncMock(spec=BaseRetriever)
        # Each retriever returns a unique document for identification
        retriever_mock.ainvoke = AsyncMock(return_value=[Document(page_content=f"Content from {ns}")])

        dp_mock = MagicMock(spec=DocumentProcessor)
        dp_mock.namespace = ns  # Store namespace for debugging
        dp_mock.vectordb = MagicMock()
        dp_mock.vectordb.as_retriever = MagicMock(return_value=retriever_mock)

        mock_document_processors_retrievers[ns] = {"dp_mock": dp_mock, "retriever_mock": retriever_mock}

    def mock_document_processor_factory(namespace: str):
        if namespace in mock_document_processors_retrievers:
            return mock_document_processors_retrievers[namespace]["dp_mock"]

        # Fallback for any unexpected namespace during testing
        # This helps if a new namespace is added to code but not yet to this mock setup
        logging.warning(
            f"Mock DocumentProcessor factory: Unmocked namespace '{namespace}' requested. Returning generic mock."
        )
        fallback_dp_mock = MagicMock(spec=DocumentProcessor)
        fallback_dp_mock.namespace = namespace  # Ensure fallback also has namespace attribute
        fallback_dp_mock.vectordb = MagicMock()
        fallback_retriever = AsyncMock(spec=BaseRetriever)
        fallback_retriever.ainvoke = AsyncMock(
            return_value=[Document(page_content=f"Fallback content for {namespace}")]
        )
        fallback_dp_mock.vectordb.as_retriever = MagicMock(return_value=fallback_retriever)
        # Store it too, so subsequent calls for the same unexpected namespace get the same mock
        mock_document_processors_retrievers[namespace] = {
            "dp_mock": fallback_dp_mock,
            "retriever_mock": fallback_retriever,
        }
        return fallback_dp_mock

    monkeypatch.setattr("app.api.orchestrator.DocumentProcessor", mock_document_processor_factory)

    return mock_llm_instance, mock_document_processors_retrievers


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch: MonkeyPatch, mock_llm_and_chains: Any):
    # mock_llm_and_chains fixture also sets up DocumentProcessor mocks, which is fine.
    orch = RagOrchestrator()

    mock_chain_itself = AsyncMock(spec=Runnable)
    mock_chain_itself.ainvoke = AsyncMock(side_effect=RuntimeError("Simulated chain error"))

    monkeypatch.setattr(orch, "summarize_chain", mock_chain_itself)
    # The session_id in the error message is not dynamically formatted from the input `session_id`
    # in the current implementation of summarize_session's error handling.
    # It uses a hardcoded placeholder string.
    assert await orch.summarize_session("sessX") == "Summary for sessX (unavailable due to error)"


def test_rag_orchestrator_has_all_dbs(mock_llm_and_chains: Any):
    # mock_llm_and_chains ensures DocumentProcessors are mocked when RagOrchestrator is instantiated.
    from app.api.orchestrator import cfg  # Import here to get patched version

    orch = RagOrchestrator()
    assert hasattr(orch, "theory_db") and orch.theory_db.namespace == cfg.CHROMA_NAMESPACE_THEORY
    assert hasattr(orch, "personal_plan_db") and orch.personal_plan_db.namespace == cfg.CHROMA_NAMESPACE_PERSONAL_PLAN
    assert hasattr(orch, "session_data_db") and orch.session_data_db.namespace == cfg.CHROMA_NAMESPACE_SESSION_DATA
    assert hasattr(orch, "future_me_db") and orch.future_me_db.namespace == cfg.CHROMA_NAMESPACE_FUTURE_ME
    assert (
        hasattr(orch, "therapist_notes_db")
        and orch.therapist_notes_db.namespace == cfg.CHROMA_NAMESPACE_THERAPIST_NOTES
    )
    assert (
        hasattr(orch, "dfm_chat_history_summaries_db")
        and orch.dfm_chat_history_summaries_db.namespace == cfg.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES
    )


# New test for _get_combined_retriever
def test_rag_orchestrator_get_combined_retriever_uses_ensemble(mock_llm_and_chains: Any):
    # mock_llm_and_chains has patched DocumentProcessor.
    # RagOrchestrator instantiation will use the mocked DocumentProcessor factory.
    from app.api.orchestrator import cfg  # Import here to get patched version

    orchestrator = RagOrchestrator()

    combined_retriever = orchestrator._get_combined_retriever()

    assert isinstance(combined_retriever, EnsembleRetriever), "Combined retriever should be an EnsembleRetriever"

    # Based on the 6 namespaces initialized in RagOrchestrator
    expected_num_retrievers = 6
    assert len(combined_retriever.retrievers) == expected_num_retrievers, (
        f"EnsembleRetriever should have {expected_num_retrievers} underlying retrievers"
    )

    # Check if the underlying retrievers are the mocked ones
    _, mock_retriever_map = mock_llm_and_chains

    # Get the actual retriever objects from the EnsembleRetriever
    actual_ensemble_components = combined_retriever.retrievers

    # Get the mocked retriever objects we expect to be in the ensemble
    expected_mocked_retrievers_in_ensemble = [
        mock_retriever_map[cfg.CHROMA_NAMESPACE_THEORY]["retriever_mock"],
        mock_retriever_map[cfg.CHROMA_NAMESPACE_PERSONAL_PLAN]["retriever_mock"],
        mock_retriever_map[cfg.CHROMA_NAMESPACE_SESSION_DATA]["retriever_mock"],
        mock_retriever_map[cfg.CHROMA_NAMESPACE_FUTURE_ME]["retriever_mock"],
        mock_retriever_map[cfg.CHROMA_NAMESPACE_THERAPIST_NOTES]["retriever_mock"],
        mock_retriever_map[cfg.CHROMA_NAMESPACE_DFM_CHAT_HISTORY_SUMMARIES]["retriever_mock"],
    ]

    for expected_mock_retriever in expected_mocked_retrievers_in_ensemble:
        assert any(expected_mock_retriever is component for component in actual_ensemble_components), (
            "Mock retriever for a namespace was not found in EnsembleRetriever components."
        )


@pytest.mark.asyncio
async def test_orchestrator_rag_path_uses_ensemble_retriever_and_formats_docs(
    monkeypatch: MonkeyPatch, mock_llm_and_chains: Any, db_session: AsyncSession
):
    from app.api.orchestrator import cfg  # Import here to get patched version

    mock_llm, mock_retriever_map = mock_llm_and_chains

    user_id = uuid.uuid4()
    mock_user = UserTable(
        id=user_id,
        email="ragtest@example.com",
        hashed_password="fake_password",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    mock_profile_data = UserProfileTable(
        user_id=user_id,
        name="Rag Test User",
        future_me_persona_summary="A hopeful future.",
        gender_identity_pronouns="they/them",
        therapeutic_setting="online",
        emotion_regulation_strengths="Breathing",
    )
    mock_safety_plan_data = SafetyPlanTable(
        user_id=user_id,
        step_1_warning_signs="Feeling down",
        step_2_internal_coping="Music",
        step_3_social_distractions="Call friend",
        step_4_help_sources="Family",
        step_5_professional_resources="Hotline",
        step_6_environment_risk_reduction="Safe space",
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
        "Name: {name}\nPersona: {future_me_persona_summary}\nPronouns: {gender_identity_pronouns}\n"
        "Strengths: {emotion_regulation_strengths}"  # Simplified for test focus
    )
    original_open_func = open  # Save original open

    def mock_open_side_effect(file_path, *args, **kwargs):
        if "system_prompt.md" in str(file_path):
            return mock_open(read_data=test_system_prompt_str)()
        elif "crisis_prompt.md" in str(file_path):  # Still mock crisis for completeness
            return mock_open(read_data="Crisis: {query} {name} {step_1_warning_signs}")()
        return original_open_func(file_path, *args, **kwargs)  # Use saved original

    monkeypatch.setattr("builtins.open", mock_open_side_effect)
    monkeypatch.setattr("app.api.orchestrator.os.path.exists", MagicMock(return_value=True))

    llm_call_args_list = []
    with patch.object(mock_llm, "ainvoke") as patched_llm_ainvoke:

        async def side_effect_for_llm_ainvoke(prompt_input_arg, *args, **kwargs):
            llm_call_args_list.append(prompt_input_arg)
            return AIMessage(content="Mocked LLM Output for RAG path")

        patched_llm_ainvoke.side_effect = side_effect_for_llm_ainvoke

        orchestrator = RagOrchestrator()
        query_text = "Tell me about my future."
        await orchestrator.answer(query_text, user=mock_user)

    # Assert that the individual (mocked) retrievers were called by the EnsembleRetriever
    theory_retriever_mock = mock_retriever_map[cfg.CHROMA_NAMESPACE_THEORY]["retriever_mock"]
    future_me_retriever_mock = mock_retriever_map[cfg.CHROMA_NAMESPACE_FUTURE_ME]["retriever_mock"]
    personal_plan_retriever_mock = mock_retriever_map[cfg.CHROMA_NAMESPACE_PERSONAL_PLAN]["retriever_mock"]

    # EnsembleRetriever calls ainvoke on its components.
    # The second argument is typically a RunnableConfig object.
    theory_retriever_mock.ainvoke.assert_called_once_with(query_text, ANY)
    future_me_retriever_mock.ainvoke.assert_called_once_with(query_text, ANY)
    personal_plan_retriever_mock.ainvoke.assert_called_once_with(query_text, ANY)
    # ... can add more for other retrievers if specific interactions are expected for all

    assert patched_llm_ainvoke.call_count > 0, "LLM ainvoke was not called"
    final_prompt_to_llm = llm_call_args_list[-1]

    prompt_string_content = ""
    if hasattr(final_prompt_to_llm, "to_string"):
        prompt_string_content = final_prompt_to_llm.to_string()
    elif hasattr(final_prompt_to_llm, "messages"):  # For ChatPromptValue
        prompt_string_content = " ".join(
            [msg.content for msg in final_prompt_to_llm.messages if hasattr(msg, "content")]
        )

    # Check that context contains content from multiple mocked sources
    assert f"Content from {cfg.CHROMA_NAMESPACE_THEORY}" in prompt_string_content
    assert f"Content from {cfg.CHROMA_NAMESPACE_FUTURE_ME}" in prompt_string_content
    assert f"Content from {cfg.CHROMA_NAMESPACE_PERSONAL_PLAN}" in prompt_string_content

    # Check for user data as well
    assert "Name: Rag Test User" in prompt_string_content
    assert "Persona: A hopeful future." in prompt_string_content
    assert "Pronouns: they/them" in prompt_string_content
    assert "Strengths: Breathing" in prompt_string_content


@pytest.mark.asyncio
async def test_orchestrator_includes_user_data_in_prompt(
    monkeypatch: MonkeyPatch, mock_llm_and_chains: Any, db_session: AsyncSession
):
    # This test can remain largely as is, focusing on user data injection.
    # The mock_llm_and_chains fixture now provides more granular retriever mocks,
    # but the core logic of this test (checking user profile data in prompt) is still valid.
    # The context part will now also include RAG data due to the EnsembleRetriever.
    from app.api.orchestrator import cfg  # Import here to get patched version

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
        emotion_regulation_strengths="Journaling, mindful breathing",
        # Added fields to match system_prompt.md and UserProfileTable
        identified_values="Connection, Growth",
        tone_alignment="Gentle",
        self_reported_goals="Feel more hopeful",
        recent_triggers_events="Stressful week",
        primary_emotional_themes="Sadness, Anxiety",
        therapist_language_to_mirror="It's okay to feel this way",
        user_emotional_tone_preference="Warm and understanding",
    )
    mock_safety_plan_data = SafetyPlanTable(
        user_id=user_id,
        step_1_warning_signs="Feeling overwhelmed",
        step_2_internal_coping="Deep breathing exercises",
        step_3_social_distractions="Call a friend",
        step_4_help_sources="Family member",
        step_5_professional_resources="Therapist number",
        step_6_environment_risk_reduction="Go for a walk",
    )

    mock_get_user_profile = AsyncMock(return_value=mock_profile_data)
    mock_get_safety_plan = AsyncMock(return_value=mock_safety_plan_data)

    monkeypatch.setattr("app.api.orchestrator.crud_profile.get_user_profile", mock_get_user_profile)
    monkeypatch.setattr("app.api.orchestrator.safety_plan_crud.get_safety_plan_by_user_id", mock_get_safety_plan)

    @asynccontextmanager
    async def mock_get_session_context():
        yield db_session

    monkeypatch.setattr("app.api.orchestrator.get_async_session_context", mock_get_session_context)

    # Use the full system prompt string from orchestrator's defaults for accuracy
    # or load from file if that's preferred for test setup.
    # For this test, let's assume the loaded prompt from file is used by RagOrchestrator.
    # The mock_open_side_effect will provide the content.

    # Using a simplified prompt string for this test to focus on user data fields
    # The actual prompt template is more complex.
    test_system_prompt_str = (
        "System Context: {context}\nUser Input: {input}\n"
        "--- User Data ---\n"
        "Name: {name}\n"
        "Profile Summary: {user_profile_summary}\n"  # This is constructed in _get_user_data_for_prompt
        "Future Persona: {future_me_persona_summary}\n"
        "Pronouns: {gender_identity_pronouns}\n"
        "Setting: {therapeutic_setting}\n"
        "Safety Plan Summary: {user_safety_plan_summary}\n"  # This is constructed
        "Values: {identified_values}\n"
        "Tone: {tone_alignment}\n"
        "Goals: {self_reported_goals}\n"
        "Triggers: {recent_triggers_events}\n"
        "Emotion Regulation Strengths: {emotion_regulation_strengths}\n"
        "Themes: {primary_emotional_themes}\n"
        "Mirror: {therapist_language_to_mirror}\n"
        "Preference: {user_emotional_tone_preference}"
    )
    test_crisis_prompt_str = (  # Keep crisis prompt mock for completeness
        "CRISIS: {query} for user {name}. Pronouns: {gender_identity_pronouns}. Strengths: {emotion_regulation_strengths}.\n"
        "Warning Signs: {step_1_warning_signs}\nInternal Coping: {step_2_internal_coping}\n"
        "Social Distractions: {step_3_social_distractions}\nHelp Sources: {step_4_help_sources}\n"
        "Professional Resources: {step_5_professional_resources}\nEnvironment Risk Reduction: {step_6_environment_risk_reduction}"
    )

    original_open_func = open

    def mock_open_side_effect(file_path, *args, **kwargs):
        if "system_prompt.md" in str(file_path):
            # For this test, we can use the actual template content if available
            # or the simplified one above. Let's use a simplified one to ensure all fields are checked.
            # If using actual template, ensure it has all these placeholders.
            # For now, using the test_system_prompt_str defined above.
            return mock_open(read_data=test_system_prompt_str)()
        elif "crisis_prompt.md" in str(file_path):
            return mock_open(read_data=test_crisis_prompt_str)()
        return original_open_func(file_path, *args, **kwargs)

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

    # Assertions for user data from UserProfileTable
    assert "Name: Test User" in prompt_string_content
    assert "Future Persona: A resilient and kind individual." in prompt_string_content
    assert "Pronouns: they/them" in prompt_string_content
    assert "Setting: online chat" in prompt_string_content
    assert "Emotion Regulation Strengths: Journaling, mindful breathing" in prompt_string_content
    assert "Values: Connection, Growth" in prompt_string_content
    assert "Tone: Gentle" in prompt_string_content
    assert "Goals: Feel more hopeful" in prompt_string_content
    assert "Triggers: Stressful week" in prompt_string_content
    assert "Themes: Sadness, Anxiety" in prompt_string_content
    assert "Mirror: It's okay to feel this way" in prompt_string_content
    assert "Preference: Warm and understanding" in prompt_string_content

    # Assertions for constructed summaries
    # user_profile_summary is "Name: Test User. Persona Summary: A resilient and kind individual."
    assert (
        "Profile Summary: Name: Test User. Persona Summary: A resilient and kind individual." in prompt_string_content
    )
    # user_safety_plan_summary is "Warning Signs: Feeling overwhelmed. Internal Coping Strategies: Deep breathing exercises."
    assert (
        "Safety Plan Summary: Warning Signs: Feeling overwhelmed. Internal Coping Strategies: Deep breathing exercises."
        in prompt_string_content
    )

    # Assertions for RAG context (will include content from mocked retrievers)
    assert f"Content from {cfg.CHROMA_NAMESPACE_THEORY}" in prompt_string_content
    assert f"Content from {cfg.CHROMA_NAMESPACE_FUTURE_ME}" in prompt_string_content


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
        emotion_regulation_strengths="Resilience, Reaching out",
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

    test_crisis_prompt_str_for_this_test = (
        "CRISIS: {query} for user {name}. Pronouns: {gender_identity_pronouns}. Strengths: {emotion_regulation_strengths}.\n"
        "Warning Signs: {step_1_warning_signs}\nInternal Coping: {step_2_internal_coping}\n"
        "Social Distractions: {step_3_social_distractions}\nHelp Sources: {step_4_help_sources}\n"
        "Professional Resources: {step_5_professional_resources}\nEnvironment Risk Reduction: {step_6_environment_risk_reduction}"
    )
    original_open_func = open

    def mock_open_crisis_test(file_path, *args, **kwargs):
        if "crisis_prompt.md" in str(file_path):
            return mock_open(read_data=test_crisis_prompt_str_for_this_test)()
        elif "system_prompt.md" in str(file_path):  # Mock system prompt as well for completeness
            return mock_open(read_data="System prompt: {input} {context} {name}")()
        return original_open_func(file_path, *args, **kwargs)

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
        await orchestrator.answer("I want to die", user=mock_user)

    assert patched_ainvoke.call_count > 0, "LLM ainvoke (patched) was not called for crisis"
    assert len(llm_call_args_list) > 0, "LLM call arguments were not captured for crisis"

    crisis_prompt_to_llm = llm_call_args_list[0]
    prompt_string_content = ""
    if hasattr(crisis_prompt_to_llm, "to_string"):
        prompt_string_content = crisis_prompt_to_llm.to_string()
    elif hasattr(crisis_prompt_to_llm, "messages"):
        prompt_string_content = " ".join(
            [msg.content for msg in crisis_prompt_to_llm.messages if hasattr(msg, "content")]
        )

    assert "user Crisis User" in prompt_string_content
    assert "Pronouns: they/them" in prompt_string_content
    assert "Strengths: Resilience, Reaching out" in prompt_string_content
    assert "Warning Signs: Feeling very down" in prompt_string_content
    assert "Internal Coping: Listen to music" in prompt_string_content
    assert "Social Distractions: Call Sam" in prompt_string_content
    assert "Help Sources: Therapist Dr. X" in prompt_string_content
    assert "Professional Resources: Hotline Y" in prompt_string_content
    assert "Environment Risk Reduction: Remove Z" in prompt_string_content
