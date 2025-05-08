"""
Alembic environment file

*   Ensures the project root is on `sys.path` so `import app.…` works.
*   Converts **async** URLs (e.g. `sqlite+aiosqlite`, `postgresql+asyncpg`)
    to their synchronous counterparts before Alembic opens a connection.
*   Binds Alembic’s `target_metadata` to the same SQLAlchemy models used
    by the application (`app.auth.models.Base`).

Run commands:

    alembic revision --autogenerate -m "describe change"
    alembic upgrade head
    alembic stamp head     # baseline an existing schema
"""

from logging.config import fileConfig
from pathlib import Path
import sys

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.future.engine import Engine

# ── Add project root so "app." imports resolve ──────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # ../../..
sys.path.append(str(PROJECT_ROOT))

from app.auth.models import Base  # noqa: E402
from app.core.settings import get_settings  # noqa: E402

# ────────────────────────────────────────────────────────────────────────
# Alembic config & metadata
# ────────────────────────────────────────────────────────────────────────
config = context.config
fileConfig(config.config_file_name)  # set up loggers

target_metadata = Base.metadata  # for autogenerate


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────
def get_sync_url() -> str:
    """
    Return a **synchronous** SQLAlchemy URL suitable for Alembic’s
    blocking engine, even if the runtime app uses an async driver.
    """
    raw = get_settings().DATABASE_URL
    url = make_url(raw)

    if url.drivername.endswith("+aiosqlite"):
        url = url.set(drivername="sqlite")
    elif url.drivername.endswith("+asyncpg"):
        url = url.set(drivername="postgresql")
    # add more driver swaps here if needed

    return str(url)


# ────────────────────────────────────────────────────────────────────────
# Offline migration (generate SQL)
# ────────────────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = get_sync_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ────────────────────────────────────────────────────────────────────────
# Online migration (connect & execute)
# ────────────────────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    connectable: Engine = create_engine(
        get_sync_url(),
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # detect column-type changes
        )

        with context.begin_transaction():
            context.run_migrations()


# ────────────────────────────────────────────────────────────────────────
# Entrypoint
# ────────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
