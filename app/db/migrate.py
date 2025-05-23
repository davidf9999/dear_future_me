# app/db/migrate.py
import asyncio

from alembic import command
from alembic.config import Config

from app.core.settings import get_settings  # Import get_settings


# Keep the original synchronous logic for potential direct CLI use or other sync contexts
def _synchronous_upgrade_head() -> None:
    """Synchronously applies Alembic migrations to 'head'."""
    print("INFO (migrate._synchronous_upgrade_head): Applying Alembic migrations...")

    # Load settings to get the actual DATABASE_URL
    settings = get_settings()
    database_url = str(settings.DATABASE_URL)  # Ensure it's a string

    print(f"INFO (migrate._synchronous_upgrade_head): Using DATABASE_URL: {database_url}")

    cfg = Config("alembic.ini")
    # Programmatically set the sqlalchemy.url in the Alembic config.
    # This overrides any value in alembic.ini, including 'env:DATABASE_URL'.
    cfg.set_main_option("sqlalchemy.url", database_url)

    try:
        command.upgrade(cfg, "head")
        print("INFO (migrate._synchronous_upgrade_head): Alembic migrations applied successfully.")
    except Exception as e:
        print(f"ERROR (migrate._synchronous_upgrade_head): Alembic upgrade failed: {e}")
        raise


async def upgrade_head() -> None:
    """
    Asynchronously applies Alembic migrations to 'head' by running
    the synchronous Alembic command in a thread pool executor.
    """
    loop = asyncio.get_running_loop()
    # Run the synchronous Alembic command in the default thread pool executor
    await loop.run_in_executor(None, _synchronous_upgrade_head)
