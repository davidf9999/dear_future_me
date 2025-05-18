# /home/dfront/code/dear_future_me/app/db/migrations/env.py
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import (
    Connection,  # Keep this for type hinting if used by do_run_migrations
)
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.auth.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
print(f"DEBUG (env.py global scope): Base.metadata.tables: {list(Base.metadata.tables.keys())}")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection_param: Connection) -> None:  # Renamed parameter
    """Configures context and runs migrations using the provided connection."""
    print(f"DEBUG (do_run_migrations): Received connection: {connection_param}")
    print("DEBUG (do_run_migrations): Configuring Alembic context with this connection.")
    context.configure(
        connection=connection_param,
        target_metadata=target_metadata,
        transaction_per_migration=True,
    )
    print("DEBUG (do_run_migrations): Starting transaction for migrations.")
    with context.begin_transaction():
        context.run_migrations()
    print("DEBUG (do_run_migrations): Migrations transaction finished.")


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Try to get connection from Alembic's config attributes (set by conftest.py)
    connectable = config.attributes.get("connection", None)
    print(f"DEBUG (run_migrations_online): Connection from config.attributes: {connectable}")

    if connectable is None:
        # Fallback for CLI: create engine from sqlalchemy.url
        print("DEBUG (run_migrations_online): No connection in attributes. Creating new engine for CLI mode.")
        db_url = config.get_main_option("sqlalchemy.url")
        if not db_url or db_url == "env:DATABASE_URL" or "%(DATABASE_URL)s" in db_url:
            resolved_env_url = os.getenv("DATABASE_URL")
            if resolved_env_url:
                db_url = resolved_env_url
            else:
                raise ValueError("Could not resolve DATABASE_URL for Alembic CLI mode.")

        engine = async_engine_from_config(
            {"sqlalchemy.url": db_url},  # Pass config directly
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
        async with engine.connect() as connection:
            print(f"DEBUG (run_migrations_online): Created new async connection: {connection}")
            # For run_sync, do_run_migrations will implicitly receive the sync connection.
            # No need to pass raw_dbapi_connection explicitly as an argument here.
            await connection.run_sync(do_run_migrations)
            # The `do_run_migrations` function expects one argument, `connection_param`,
            # which `run_sync` provides as the underlying synchronous connection.
        await engine.dispose()
        print("DEBUG (run_migrations_online): Disposed newly created engine for CLI mode.")
    else:
        # Path for programmatic call from conftest.py
        # `connectable` here is the underlying synchronous DBAPI connection
        # passed via alembic_cfg.attributes['connection']
        print(
            f"DEBUG (run_migrations_online): Using pre-configured synchronous connection: {connectable}. Calling do_run_migrations directly."
        )
        do_run_migrations(connectable)


if context.is_offline_mode():
    run_migrations_offline()
else:
    if config.attributes.get("connection", None) is None:  # Only run asyncio.run if not in programmatic test mode
        asyncio.run(run_migrations_online())
    else:
        # If connection is in attributes, we're in programmatic test mode.
        # alembic_command.upgrade (sync) is calling this script.
        # The `else` block in `run_migrations_online` which calls `do_run_migrations(connectable)`
        # will be executed.
        pass
