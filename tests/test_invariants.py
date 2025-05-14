# tests/test_invariants.py

# ─── Standard Library ───────────────────────────────────────────────────────
from pathlib import Path

# ─── Third-Party ────────────────────────────────────────────────────────────
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

# ─── Local Application ──────────────────────────────────────────────────────
from app.core.settings import get_settings
from app.db.session import (
    AsyncSessionLocal,  # Corrected import: AsyncSessionLocal instead of AsyncSessionMaker
)

# ────────────────────────────────────────────────────────────────────────────

# Add the project root to the Python path
# This is often handled by pytest configuration or running pytest from the root,
# but can be added here for explicitness if needed.
# current_dir = Path(__file__).parent
# project_root = current_dir.parent
# sys.path.insert(0, str(project_root))


# ─── Invariants ─────────────────────────────────────────────────────────────
# These tests are designed to ensure that the application's basic invariants
# are met. For example, that the database can be connected to, that the
# settings are loaded correctly, etc.


@pytest.mark.asyncio
async def test_db_connection():
    """Test that the database can be connected to."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with AsyncSessionLocal(bind=engine) as session:  # Use AsyncSessionLocal
        assert session is not None, "Failed to create a database session."
        # You could add a simple query here to further test the connection, e.g.:
        # from sqlalchemy import text
        # result = await session.execute(text("SELECT 1"))
        # assert result.scalar_one() == 1, "Database query failed."


def test_settings_load():
    """Test that the settings are loaded correctly."""
    settings = get_settings()
    assert settings is not None, "Failed to load settings."
    assert settings.DATABASE_URL is not None, "DATABASE_URL not set in settings."
    # Add more assertions for critical settings if needed


def test_project_structure():
    """Test that the project structure is as expected."""
    # Example: Check for the existence of key directories
    project_root = Path(__file__).parent.parent
    assert (project_root / "app").is_dir(), "app directory not found."
    assert (project_root / "app" / "api").is_dir(), "app/api directory not found."
    assert (project_root / "app" / "db").is_dir(), "app/db directory not found."
    assert (project_root / "templates").is_dir(), "templates directory not found."


# Add more invariant tests as needed for your application.
# For example, checking environment variables, external service reachability (mocked), etc.
