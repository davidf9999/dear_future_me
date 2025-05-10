# app/cli.py
"""
app/cli.py
~~~~~~~~~~

Command-Line Interface for Dear-Future-Me application.
Provides interactive chat and RAG administration utilities.
"""

from __future__ import annotations

import asyncio
import os
import sys  # Keep sys for stderr
import uuid
from typing import Optional

import click
import httpx  # AsyncAPI will use this
from dotenv import load_dotenv
from rich.console import Console
from rich.text import Text

# Assuming app.clients.api_client and app.core.settings are findable
# If running with `python -m app.cli`, Python handles the path.
from app.clients.api_client import AsyncAPI
from app.core.settings import Settings, get_settings
from app.rag.processor import DocumentProcessor  # For RAG admin commands

# --------------------------------------------------------------------------- #
# Environment & constants
# --------------------------------------------------------------------------- #

load_dotenv()
try:
    cfg: Settings = get_settings()
except Exception as e:
    print(f"FATAL: Could not load settings. Check .env file. Error: {e}", file=sys.stderr)
    sys.exit(1)


API_URL = os.getenv("DFM_API_URL", "http://localhost:8000")
# CLIENT_DEMO_MODE for CLI now primarily dictates if it tries to use the .env demo user
CLIENT_DEMO_MODE = cfg.DEMO_MODE
CURRENT_LANG = cfg.APP_DEFAULT_LANGUAGE

# --------------------------------------------------------------------------- #
# UI Strings for CLI (simple i18n)
# --------------------------------------------------------------------------- #
UI_STRINGS = {
    "en": {
        "greeting_banner": "[bold]Dear-Future-Me interactive chat (type 'exit' to quit)[/bold]",
        "type_exit_prompt": "Type 'exit' to quit.\n",
        "user_prompt": "[bold cyan]you:[/bold cyan] ",
        "ai_prompt": "[bold cyan]ai:[/bold cyan] ",
        "bye_message": "\n[bold]Bye![/bold]",
        "auth_failed_exit": "[bold red]Authentication failed. Cannot start chat session. Exiting.[/bold red]",
        "auth_failed_check_server": "[bold yellow]Please check server logs and ensure the server is running and accessible.[/bold yellow]",
        "auth_failed_check_env_demo": f"[bold yellow]Ensure DEMO_USER_EMAIL ({cfg.DEMO_USER_EMAIL}) and DEMO_USER_PASSWORD are correctly set in your .env file if using CLIENT_DEMO_MODE.[/bold yellow]",
        "auth_critical_error": "[bold red]Critical error during authentication setup: {error}[/bold red]",
        "auth_cannot_start": "[bold red]Could not authenticate. Chat session cannot start.[/bold red]\n",
        "http_error_from_server": "[bold red]Oops! HTTP error from server: {status_code} - {text}[/bold red]",
        "session_expired_error": "[bold yellow]Your session might have expired or token is invalid. Try restarting the CLI.[/bold yellow]",
        "generic_comms_error": "[bold red]Oops! Something went wrong on the server side or during communication.[/bold red]",
        "details_to_stderr": "(Details logged to stderr)",
        "attempting_demo_user_setup": "[dim]CLIENT_DEMO_MODE is True. Attempting to use predefined demo user: {email}...[/dim]",
        "attempting_temp_user_setup": "[dim]CLIENT_DEMO_MODE is False. Attempting to register/login temporary user: {email}...[/dim]",
        "login_success": "[green]Successfully logged in as {email}[/green]",
        "login_failed_attempt_register": "[yellow]Login failed for {email} (status {status_code}). Attempting to register...[/yellow]",
        "user_registered_logging_in": "[green]User {email} registered. Logging in...[/green]",
        "login_success_after_register": "[green]Successfully logged in as {email} after registration[/green]",
        "registration_failed": "[red]Registration for {email} failed (status {status_code}): {text}[/red]",
        "login_error_other": "[red]Login error for {email} (status {status_code}): {text}[/red]",
        "unexpected_auth_error": "[red]Unexpected error during auth setup for {email}: {error}[/red]",
        "authenticated_as_banner": "[bold green]Authenticated as {email}[/bold green]\n",
        "rag_ingest_start": "[bold blue]Starting RAG ingestion for namespace '{namespace}' from directory '{source_dir}'...[/bold blue]",
        "rag_ingest_success": "[bold green]Ingestion complete. Processed {count} documents for namespace '{namespace}'.[/bold green]",
        "rag_ingest_error_file": "[red]  Error ingesting {filename}: {error}[/red]",
        "rag_ingest_error_general": "[bold red]An error occurred during RAG ingestion: {error}[/bold red]",
        "rag_ingested_file": "  Ingested: {filename} as {doc_id}",
    },
    "he": {
        "greeting_banner": "[bold]צ'אט אינטראקטיבי עם 'אני מהעתיד' (הקלד 'צא' ליציאה)[/bold]",
        "type_exit_prompt": "הקלד 'צא' ליציאה.\n",
        "user_prompt": "[bold cyan]את/ה:[/bold cyan] ",
        "ai_prompt": "[bold cyan]אני מהעתיד:[/bold cyan] ",
        "bye_message": "\n[bold]להתראות![/bold]",
        "auth_failed_exit": "[bold red]האימות נכשל. לא ניתן להתחיל סשן צ'אט. יוצא.[/bold red]",
        "auth_failed_check_server": "[bold yellow]אנא בדוק/בדקי את יומני השרת וודא/י שהשרת פועל ונגיש.[/bold yellow]",
        "auth_failed_check_env_demo": f"[bold yellow]ודא/י ש-DEMO_USER_EMAIL ({cfg.DEMO_USER_EMAIL}) ו-DEMO_USER_PASSWORD מוגדרים כראוי בקובץ .env שלך אם משתמשים ב-CLIENT_DEMO_MODE.[/bold yellow]",
        "auth_critical_error": "[bold red]שגיאה קריטית במהלך הגדרת האימות: {error}[/bold red]",
        "auth_cannot_start": "[bold red]לא ניתן היה לאמת. סשן הצ'אט לא יכול להתחיל.[/bold red]\n",
        "http_error_from_server": "[bold red]אופס! שגיאת HTTP מהשרת: {status_code} - {text}[/bold red]",
        "session_expired_error": "[bold yellow]יתכן שהסשן שלך פג או שהטוקן אינו חוקי. נסה/י להפעיל מחדש את ה-CLI.[/bold yellow]",
        "generic_comms_error": "[bold red]אופס! משהו השתבש בצד השרת או במהלך התקשורת.[/bold red]",
        "details_to_stderr": "(פרטים נרשמו ל-stderr)",
        "attempting_demo_user_setup": "[dim]CLIENT_DEMO_MODE הוא True. מנסה להשתמש במשתמש הדגמה מוגדר מראש: {email}...[/dim]",
        "attempting_temp_user_setup": "[dim]CLIENT_DEMO_MODE הוא False. מנסה לרשום/להתחבר למשתמש זמני: {email}...[/dim]",
        "login_success": "[green]התחברת בהצלחה כ-{email}[/green]",
        "login_failed_attempt_register": "[yellow]ההתחברות עבור {email} נכשלה (סטטוס {status_code}). מנסה להירשם...[/yellow]",
        "user_registered_logging_in": "[green]משתמש {email} נרשם. מתחבר...[/green]",
        "login_success_after_register": "[green]התחברת בהצלחה כ-{email} לאחר ההרשמה[/green]",
        "registration_failed": "[red]ההרשמה עבור {email} נכשלה (סטטוס {status_code}): {text}[/red]",
        "login_error_other": "[red]שגיאת התחברות עבור {email} (סטטוס {status_code}): {text}[/red]",
        "unexpected_auth_error": "[red]שגיאה לא צפויה במהלך הגדרת האימות עבור {email}: {error}[/red]",
        "authenticated_as_banner": "[bold green]מאומת/ת כ-{email}[/bold green]\n",
        "rag_ingest_start": "[bold blue]מתחיל הטמעת RAG עבור מרחב השם '{namespace}' מהספרייה '{source_dir}'...[/bold blue]",
        "rag_ingest_success": "[bold green]ההטמעה הושלמה. עובדו {count} מסמכים עבור מרחב השם '{namespace}'.[/bold green]",
        "rag_ingest_error_file": "[red]  שגיאה בהטמעת {filename}: {error}[/red]",
        "rag_ingest_error_general": "[bold red]אירעה שגיאה במהלך הטמעת RAG: {error}[/bold red]",
        "rag_ingested_file": "  הוטמע: {filename} כ-{doc_id}",
    },
}
STR = UI_STRINGS.get(CURRENT_LANG, UI_STRINGS["en"])  # Fallback to English if lang not found
console = Console()  # Global console instance

# --------------------------------------------------------------------------- #
# Authentication Helper for CLI
# --------------------------------------------------------------------------- #


async def setup_cli_session_auth(api_client: AsyncAPI) -> Optional[str]:
    """
    Handles authentication for the CLI session using the provided AsyncAPI client.
    If CLIENT_DEMO_MODE is true, attempts to register/login the predefined demo user from settings.
    Otherwise, registers and logs in a new random temporary user.
    Returns the token or None if auth fails, and updates api_client._token.
    """
    if CLIENT_DEMO_MODE:
        email = cfg.DEMO_USER_EMAIL
        password = cfg.DEMO_USER_PASSWORD
        console.print(STR["attempting_demo_user_setup"].format(email=email))
    else:
        email = f"temp_cli_user_{uuid.uuid4().hex[:8]}@example.com"
        password = "cli_temppassword"
        console.print(STR["attempting_temp_user_setup"].format(email=email))

    try:
        # Try to login first
        token = await api_client.login(email, password)
        console.print(STR["login_success"].format(email=email))
        return token
    except httpx.HTTPStatusError as login_err:
        if login_err.response.status_code == 400:  # Bad credentials or user not found
            console.print(
                STR["login_failed_attempt_register"].format(email=email, status_code=login_err.response.status_code)
            )
            try:
                await api_client.register(
                    email,
                    password,
                    first_name="CLI",
                    last_name="User" if not CLIENT_DEMO_MODE else "Demo",
                )
                console.print(STR["user_registered_logging_in"].format(email=email))
                token = await api_client.login(email, password)  # Try login again
                console.print(STR["login_success_after_register"].format(email=email))
                return token
            except httpx.HTTPStatusError as reg_err:
                console.print(
                    STR["registration_failed"].format(
                        email=email, status_code=reg_err.response.status_code, text=reg_err.response.text
                    )
                )
                return None
        else:  # Other login errors
            console.print(
                STR["login_error_other"].format(
                    email=email, status_code=login_err.response.status_code, text=login_err.response.text
                )
            )
            return None
    except Exception as e:
        console.print(STR["unexpected_auth_error"].format(email=email, error=e))
        import traceback

        traceback.print_exc(file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# CLI definition (click)
# --------------------------------------------------------------------------- #


@click.group()
def cli() -> None:
    """Dear-Future-Me utility CLI."""
    pass


# --- RAG Administration Command Group ---
@cli.group(help="Manage RAG knowledge base.")
def rag():
    """Commands for RAG administration."""
    pass


@rag.command(help="Ingest and index documents from a specified source into a RAG namespace.")
@click.option(
    "--namespace",
    required=True,
    type=click.Choice(
        [
            cfg.CHROMA_NAMESPACE_THEORY,
            cfg.CHROMA_NAMESPACE_PLAN,
            cfg.CHROMA_NAMESPACE_SESSION,
            cfg.CHROMA_NAMESPACE_FUTURE,
        ],
        case_sensitive=False,
    ),
    help="The RAG namespace to ingest into.",
)
@click.option(
    "--source-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True, readable=True),
    help="Directory containing documents to ingest.",
)
@click.option("--doc-id-prefix", default="doc", show_default=True, help="Prefix for document IDs.")
@click.option(
    "--file-extensions",
    default=".txt,.md",
    show_default=True,
    help="Comma-separated list of file extensions to process (e.g., .txt,.md).",
)
def ingest(namespace: str, source_dir: str, doc_id_prefix: str, file_extensions: str):
    """
    Processes text files from source_dir and ingests them into the specified RAG namespace.
    This is a synchronous operation for simplicity in a CLI admin command.
    """
    console.print(STR["rag_ingest_start"].format(namespace=namespace, source_dir=source_dir))
    valid_extensions = [ext.strip() for ext in file_extensions.split(",")]
    try:
        # Note: DocumentProcessor uses OpenAIEmbeddings by default, which costs money.
        # Consider allowing configuration for local/free embedding models for admin tasks.
        processor = DocumentProcessor(namespace=namespace)  # Uses settings from cfg

        count = 0
        for filename in os.listdir(source_dir):
            if any(filename.endswith(ext) for ext in valid_extensions):
                file_path = os.path.join(source_dir, filename)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text_content = f.read()
                    # Create a more unique doc_id, perhaps incorporating part of the filename
                    base_filename = os.path.splitext(filename)[0].replace(" ", "_").lower()
                    doc_id = f"{doc_id_prefix}_{base_filename}_{count + 1}"
                    processor.ingest(doc_id=doc_id, text=text_content, metadata={"source_file": filename})
                    console.print(STR["rag_ingested_file"].format(filename=filename, doc_id=doc_id))
                    count += 1
                except Exception as e:
                    console.print(STR["rag_ingest_error_file"].format(filename=filename, error=e))
        console.print(STR["rag_ingest_success"].format(count=count, namespace=namespace))
    except Exception as e:
        console.print(STR["rag_ingest_error_general"].format(error=e))
        import traceback

        traceback.print_exc(file=sys.stderr)


@cli.command(help="Interactive chat with the running API server.")
@click.option(
    "--url",
    default=API_URL,
    show_default=True,
    help="Base URL of the FastAPI server.",
)
async def chat(url: str) -> None:  # Make the command itself async
    """Start an interactive chat session."""
    api = AsyncAPI(url)  # Instantiate the new AsyncAPI client

    async def _run_chat_logic() -> None:  # Renamed internal function for clarity
        # ------------------------------------------------------------------ auth
        try:
            token = await setup_cli_session_auth(api)  # Pass the api instance
            if not token:
                console.print(STR["auth_failed_exit"])
                console.print(STR["auth_failed_check_server"])
                if CLIENT_DEMO_MODE:
                    console.print(STR["auth_failed_check_env_demo"])
                return

            user_email_for_banner = cfg.DEMO_USER_EMAIL if CLIENT_DEMO_MODE and api._token else "authenticated user"
            banner = STR["authenticated_as_banner"].format(email=user_email_for_banner)
        except Exception as e:
            console.print(STR["auth_critical_error"].format(error=e))
            banner = STR["auth_cannot_start"]
            console.print(banner)
            return

        console.print(banner + STR["greeting_banner"])
        console.print(STR["type_exit_prompt"])

        # ------------------------------------------------------------------ loop
        try:
            while True:
                try:
                    query = await asyncio.to_thread(console.input, STR["user_prompt"])
                    query = query.strip()
                except (KeyboardInterrupt, EOFError):
                    console.print(STR["bye_message"])
                    break

                if query.lower() in {"exit", "quit", "צא"}:  # Added Hebrew exit command
                    console.print(STR["bye_message"])
                    break

                if not query:  # Skip empty input
                    continue

                try:
                    answer = await api.chat(query)  # Use the AsyncAPI's chat method
                except httpx.HTTPStatusError as ex_http:
                    console.print(
                        STR["http_error_from_server"].format(
                            status_code=ex_http.response.status_code, text=ex_http.response.text
                        )
                    )
                    if ex_http.response.status_code == 401:  # Unauthorized
                        console.print(STR["session_expired_error"])
                except Exception as ex:  # Catch other exceptions during chat call
                    console.print(STR["generic_comms_error"])
                    console.print(STR["details_to_stderr"])
                    print("----- TRACEBACK -----", file=sys.stderr)
                    import traceback

                    traceback.print_exception(ex, file=sys.stderr)
                    break  # Break on unexpected errors

                console.print(Text(STR["ai_prompt"], style="bold cyan"), answer)
        finally:
            await api.close()  # Ensure API client is closed

    await _run_chat_logic()


@cli.result_callback()
def process_result(result, **kwargs):
    """
    Handles the result of a Click command.
    If an async command was run, Click's default runner awaits it.
    This callback is mostly for potential future use or cleanup if needed.
    """
    # If result is a coroutine, it should have been awaited by Click's runner
    # for async commands.
    pass


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #


def main():
    """
    Main entry point for the CLI.
    Handles Click's async command execution.
    """
    # Click's default behavior for `cli.main()` when `cli` contains async commands
    # is to handle the asyncio event loop.
    # We pass `standalone_mode=False` if we were to call this programmatically
    # and manage the loop ourselves, but for direct script execution,
    # `cli()` or `cli.main()` is usually sufficient.
    # Let Click manage its own loop for async commands.
    cli()


if __name__ == "__main__":
    # To run this CLI directly:
    # `python -m app.cli chat`
    # `python -m app.cli rag ingest --namespace theory --source-dir ./data/theory_docs`
    main()
