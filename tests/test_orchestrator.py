# tests/test_orchestrator.py
import pytest
from app.api.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_orchestrator_answer(monkeypatch):
    # Mock RAG chain to return fixed value
    class DummyChain:
        async def arun(self, q):
            return "42"

    orch = Orchestrator()
    monkeypatch.setattr(orch, "chain", DummyChain())
    reply = await orch.answer("anything")
    assert reply == "42"
