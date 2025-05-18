# /home/dfront/code/dear_future_me/app/db/migrations/env.py
import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.auth.models import Base as AuthBase

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line needs to be placed early in the script so that
# Python logging is configured before any loggers are created.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = AuthBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # In offline mode, we get the URL directly.
    # This should be the resolved URL if alembic.ini uses interpolation
    # and the necessary env var is set.
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        transaction_per_migration=False,  # Explicitly set for SQLite, helps with DDL visibility
    )

    with context.begin_transaction():  # This transaction is now per migration
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Get the sqlalchemy.url. This will retrieve the value set programmatically
    # by app.db.migrate._synchronous_upgrade_head when called from tests,
    # or the value from alembic.ini (potentially interpolated) when run from CLI.
    db_url = config.get_main_option("sqlalchemy.url")

    if not db_url or db_url == "env:DATABASE_URL" or "%(DATABASE_URL)s" in db_url:
        # If db_url is still a placeholder, try to resolve it from environment
        # This is a fallback for direct CLI usage if alembic.ini placeholders weren't resolved
        # by the Config object itself (which can happen depending on Alembic/ConfigParser versions)
        resolved_env_url = os.getenv("DATABASE_URL")
        if resolved_env_url:
            db_url = resolved_env_url
        else:
            # If still not resolved, raise an error as we need a concrete URL.
            raise ValueError(
                f"Could not resolve a valid SQLAlchemy URL. "
                f"Attempted to use '{db_url}' from Alembic config/env. "
                "Ensure DATABASE_URL environment variable is set for CLI use, "
                "or that it's correctly passed programmatically."
            )

    # Create a configuration dictionary specifically for async_engine_from_config
    # using the resolved database URL.
    engine_config_dict = {
        "sqlalchemy.url": db_url,
        # You can add other engine-specific options here if they are in your
        # [alembic] section of alembic.ini and need to be passed, e.g.:
        # "pool_pre_ping": config.get_main_option("pool_pre_ping", "True"),
    }

    connectable = async_engine_from_config(
        engine_config_dict,  # Pass the dictionary with the resolved URL
        prefix="sqlalchemy.",  # Standard prefix for SQLAlchemy options
        poolclass=pool.NullPool,  # Standard for Alembic's online mode
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    # This will run in a separate thread when called via upgrade_head() from tests,
    # so it's safe to create a new event loop here.
    # For direct CLI `alembic upgrade head`, this is also the standard way.
    asyncio.run(run_migrations_online())
