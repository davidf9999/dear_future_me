# tests/test_invariants.py
"""
Invariant checks that replace the old ad-hoc `check_*` helper scripts.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.router import get_jwt_strategy
from app.core.settings import get_settings
from app.db.session import get_async_session, AsyncSessionMaker


# ─────────────────────────  routing invariants  ─────────────────────────
def test_auth_routes_present():
    client = TestClient(app)
    assert client.post("/auth/login").status_code != 404
    assert client.post("/auth/register").status_code != 404


def test_jwt_strategy_secret_matches_settings():
    strat = get_jwt_strategy()
    assert strat.secret == get_settings().SECRET_KEY


# ──────────────────────────  DB invariants  ────────────────────────────
@pytest.mark.asyncio
async def test_singleton_engine():
    from app.db.session import engine  # local import to avoid early side-effects

    # async_sessionmaker stores constructor args in .kw
    assert AsyncSessionMaker.kw.get("bind") is engine

    # Two sessions pulled from dependency share the same engine
    async for s1 in get_async_session():
        async for s2 in get_async_session():
            assert s1.bind is s2.bind is engine
            break
        break
