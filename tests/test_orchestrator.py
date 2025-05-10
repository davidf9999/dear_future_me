# tests/test_orchestrator.py

from unittest.mock import AsyncMock

import pytest

from app.api.orchestrator import Orchestrator, RagOrchestrator


@pytest.mark.asyncio
async def test_non_risk_uses_rag_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: False)

    mock_rag_chain = AsyncMock()
    mock_rag_chain.ainvoke = AsyncMock(return_value={"answer": "RAG→OK"})

    monkeypatch.setattr(orch, "_rag_chain", mock_rag_chain)

    assert await orch.answer("hello") == "RAG→OK"


@pytest.mark.asyncio
async def test_risk_uses_crisis_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: True)

    mock_crisis_chain = AsyncMock()
    mock_crisis_chain.ainvoke = AsyncMock(return_value={"result": "CRISIS!!!"})

    monkeypatch.setattr(orch, "_crisis_chain", mock_crisis_chain)

    assert await orch.answer("I want to die") == "CRISIS!!!"


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch):
    orch = Orchestrator()

    # Mock the branching chain itself to raise an error
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
    # Optionally, check its type:
    from app.rag.processor import DocumentProcessor

    assert isinstance(orch.future_db, DocumentProcessor)


def test_detect_risk_functionality():
    orch = Orchestrator()
    assert orch._detect_risk("I want to die") is True
    assert orch._detect_risk("I feel HOPELESS sometimes") is True
    assert orch._detect_risk("I am happy today") is False
    assert orch._detect_risk("") is False
