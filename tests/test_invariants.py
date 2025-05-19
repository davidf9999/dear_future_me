# tests/test_invariants.py
"""
Invariant checks that replace the old ad-hoc `check_*` helper scripts.
"""

import pytest

from app.auth.router import get_jwt_strategy
from app.core.settings import get_settings
from app.db.session import AsyncSessionMaker  # engine was locally imported
from app.db.session import engine, get_async_session

# from app.main import app


# ─────────────────────────  routing invariants  ─────────────────────────
# @pytest.mark.demo_mode(False)  # This test needs registration route present
# def test_auth_routes_present(client: TestClient):
#     assert client.post("/auth/login").status_code != 404
#     assert client.post("/auth/register").status_code != 404
# or
# @pytest.mark.asyncio
# async def test_auth_routes_present(client: TestClient):
#     """Checks if standard FastAPI Users auth routes are present."""
#     app = client.app # Get the FastAPI app instance from the TestClient
#     router_paths = {route.path for route in app.routes if hasattr(route, 'path')}
#     # print("DEBUG: Discovered router paths:", router_paths)
#     assert "/auth/login" in router_paths
#     assert "/auth/logout" in router_paths
#     assert "/auth/register" in router_paths


def test_jwt_strategy_secret_matches_settings():
    strat = get_jwt_strategy()
    assert strat.secret == get_settings().SECRET_KEY


# ──────────────────────────  DB invariants  ────────────────────────────
@pytest.mark.asyncio
async def test_singleton_engine():
    # engine is now imported at the top
    # async_sessionmaker stores constructor args in .kw
    assert AsyncSessionMaker.kw.get("bind") is engine

    # Two sessions pulled from dependency share the same engine
    async for s1 in get_async_session():
        async for s2 in get_async_session():
            assert s1.bind is s2.bind is engine
            break
        break
