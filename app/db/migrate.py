# app/db/migrate.py
"""
Utility to run `alembic upgrade head` programmatically.

Usage:
    python -m app.db.migrate   # upgrades to latest head
"""

from pathlib import Path

from alembic import command
from alembic.config import Config


def upgrade_head() -> None:
    cfg = Config(str(Path(__file__).parent.parent.parent / "alembic.ini"))
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    upgrade_head()
