# tests/test_invariants.py
"""
Invariant checks that replace the old ad-hoc `check_*` helper scripts.
"""

from fastapi.testclient import TestClient

from app.main import app
from app.auth.router import get_jwt_strategy
from app.core.settings import get_settings
from app.db.session import get_async_session, AsyncSessionMaker


# ────────────────────────────────────────────────────────────────
# Auth & routing invariants
# ────────────────────────────────────────────────────────────────
def test_auth_routes_present():
    """
    Ensure the core FastAPI-Users endpoints are still wired up.
    If their paths change we want an immediate CI failure.
    """
    client = TestClient(app)
    # 422 is fine here – we only care that the route exists.
    assert client.post("/auth/login").status_code != 404
    assert client.post("/auth/register").status_code != 404


def test_jwt_strategy_secret_matches_settings():
    """
    The JWT Strategy must use the same SECRET_KEY defined in Settings.
    """
    strat = get_jwt_strategy()
    assert strat.secret == get_settings().SECRET_KEY


# ────────────────────────────────────────────────────────────────
# DB-layer invariants
# ────────────────────────────────────────────────────────────────
async def test_singleton_engine():
    """
    `AsyncSessionMaker.bind` should be the one global `engine`
    created in app.db.session (verifies we didn't accidentally
    re-instantiate it).
    """
    from app.db.session import engine  # import inside to avoid circulars

    assert AsyncSessionMaker.bind is engine

    # Create two sessions and confirm they share the same engine object.
    async for s1 in get_async_session():
        async for s2 in get_async_session():
            assert s1.bind is s2.bind is engine
            break
        break
