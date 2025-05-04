import pytest
from app.api.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_answer(monkeypatch):
    class DummyChain:
        async def arun(self, q):
            return "42"

    orch = Orchestrator()
    monkeypatch.setattr(orch, "chain", DummyChain())
    reply = await orch.answer("anything")
    assert reply == "42"


@pytest.mark.asyncio
async def test_answer_fallback_on_error(monkeypatch):
    orch = Orchestrator()

    # stub chain to always raise
    class BadChain:
        async def arun(self, q):
            raise RuntimeError("boom")

    monkeypatch.setattr(orch, "chain", BadChain())

    reply = await orch.answer("anything")
    assert (
        reply
        == "I’m sorry, I’m unable to answer that right now. Please try again later."
    )