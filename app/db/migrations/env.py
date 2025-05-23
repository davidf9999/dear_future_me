# app/db/migrations/env.py
import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Add the project root directory to sys.path
# This allows Alembic to find the 'app' module
# This block is placed after standard library and third-party library imports,
# but before any application-specific imports that depend on this path modification.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.auth.models import Base  # noqa: E402 # This import will now work

# Alembic Config object, which provides access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata
# print(f"DEBUG (env.py global scope): Base.metadata.tables: {list(Base.metadata.tables.keys())}")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection_param: Connection) -> None:
    """Configures context and runs migrations using the provided connection."""
    # print(f"DEBUG (do_run_migrations): Received connection: {connection_param}")
    context.configure(
        connection=connection_param,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()
    # print("DEBUG (do_run_migrations): Migrations transaction finished.")


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = config.attributes.get("connection", None)
    # print(f"DEBUG (run_migrations_online): Connection from config.attributes: {connectable}")

    if connectable is None:
        # print("DEBUG (run_migrations_online): No connection in attributes. Creating new engine for CLI mode.")
        db_url = config.get_main_option("sqlalchemy.url")
        if not db_url or db_url == "env:DATABASE_URL" or "%(DATABASE_URL)s" in db_url:
            resolved_env_url = os.getenv("DATABASE_URL")
            if resolved_env_url:
                db_url = resolved_env_url
            else:
                raise ValueError("Could not resolve DATABASE_URL for Alembic CLI mode.")

        engine = async_engine_from_config(
            {"sqlalchemy.url": db_url},
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        async with engine.connect() as connection:
            # print(f"DEBUG (run_migrations_online): Created new async connection: {connection}")
            await connection.run_sync(do_run_migrations)

        await engine.dispose()
        # print("DEBUG (run_migrations_online): Disposed newly created engine for CLI mode.")
    else:
        # print(
        # f"DEBUG (run_migrations_online): Using pre-configured synchronous connection: {connectable}. Calling do_run_migrations directly."
        # )
        do_run_migrations(connectable)


if context.is_offline_mode():
    run_migrations_offline()
else:
    if config.attributes.get("connection", None) is None:
        asyncio.run(run_migrations_online())
    else:
        pass
