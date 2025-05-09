# tests/test_orchestrator.py

import pytest

from app.api.orchestrator import Orchestrator, RagOrchestrator


@pytest.mark.asyncio
async def test_non_risk_uses_rag_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: False)

    async def fake_rag(q):
        return "RAG→OK"

    monkeypatch.setattr(orch._rag_chain, "arun", fake_rag)

    assert await orch.answer("hello") == "RAG→OK"


@pytest.mark.asyncio
async def test_risk_uses_crisis_chain(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "_detect_risk", lambda q: True)

    async def fake_crisis(q):
        return "CRISIS!!!"

    monkeypatch.setattr(orch._crisis_chain, "arun", fake_crisis)

    assert await orch.answer("I want to die") == "CRISIS!!!"


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch):
    orch = Orchestrator()

    class Bad:
        async def arun(self, q):
            raise RuntimeError

    orch.chain = Bad()
    assert await orch.answer("anything") == "I’m sorry, I’m unable to answer that right now. Please try again later."


@pytest.mark.asyncio
async def test_summarize_session_success(monkeypatch):
    orch = RagOrchestrator()

    class DummyQA:
        async def arun(self, sid):
            return "SESSION SUMMARY"

    orch.session_db.qa = DummyQA()

    assert await orch.summarize_session("sess1") == "SESSION SUMMARY"


@pytest.mark.asyncio
async def test_summarize_session_fallback(monkeypatch):
    orch = RagOrchestrator()

    class BadQA:
        async def arun(self, sid):
            raise RuntimeError

    orch.session_db.qa = BadQA()

    assert await orch.summarize_session("sessX") == "Summary for sessX"


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
