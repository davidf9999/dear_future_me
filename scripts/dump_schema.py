# /home/dfront/code/dear_future_me/scripts/dump_schema.py
# Full file content
import logging
import sqlite3

from app.core.settings import get_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def dump_db_schema():
    """
    Connects to the SQLite database defined in settings and prints its schema.
    """
    settings = get_settings()
    db_url = settings.DATABASE_URL

    if not db_url.startswith("sqlite"):
        logger.error(f"This script is designed for SQLite databases. Current DATABASE_URL is: {db_url}")
        print(f"Error: This script only supports SQLite. Your current database is not SQLite: {db_url}")
        return

    # Extract database file path from URL (e.g., "sqlite+aiosqlite:///./test.db" -> "./test.db")
    db_path = db_url.split("///")[-1]
    if not db_path:
        logger.error(f"Could not determine SQLite database file path from URL: {db_url}")
        print(f"Error: Could not parse database path from URL: {db_url}")
        return

    logger.info(f"Connecting to SQLite database at: {db_path}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        logger.info("Fetching schema information...")
        # Query sqlite_master for schema information
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables_schema = cursor.fetchall()

        cursor.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
        indexes_schema = cursor.fetchall()

        conn.close()

        if not tables_schema and not indexes_schema:
            logger.warning(f"No user-defined tables or indexes found in the database: {db_path}")
            print(f"-- No user-defined tables or indexes found in {db_path}")
            return

        print(f"-- Schema for SQLite database: {db_path}\n")
        for schema_item in tables_schema:
            if schema_item[0]:
                print(f"{schema_item[0]};")

        if indexes_schema:
            print("\n-- Indexes:")
            for schema_item in indexes_schema:
                if schema_item[0]:
                    print(f"{schema_item[0]};")

        logger.info("Schema dump completed.")

    except sqlite3.Error as e:
        logger.error(f"SQLite error occurred: {e}")
        print(f"SQLite error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    dump_db_schema()
