# app/cli.py
"""
app/cli.py
~~~~~~~~~~

Small helper CLI for local demo & smoke-tests.
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
# If running `python app/cli.py` directly, ensure project root is in PYTHONPATH or use sys.path manipulation (removed for now for linter).
from app.clients.api_client import AsyncAPI
from app.core.settings import Settings, get_settings

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


@cli.command(help="Interactive chat with the running API server.")
@click.option(
    "--url",
    default=API_URL,
    show_default=True,
    help="Base URL of the FastAPI server.",
)
def chat(url: str) -> None:
    """Start an interactive chat session."""
    api = AsyncAPI(url)  # Instantiate the new AsyncAPI client

    async def _run() -> None:
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
        while True:
            try:
                query = console.input(STR["user_prompt"]).strip()
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
            except Exception as ex:
                console.print(STR["generic_comms_error"])
                console.print(STR["details_to_stderr"])
                print("----- TRACEBACK -----", file=sys.stderr)
                import traceback

                traceback.print_exception(ex, file=sys.stderr)
                break  # Break on unexpected errors

            console.print(Text(STR["ai_prompt"], style="bold cyan"), answer)

        await api.close()  # Use the AsyncAPI's close method

    try:
        asyncio.run(_run())
    except RuntimeError as e:
        if "Event loop is closed" not in str(e):  # Avoid error if loop already closed
            raise
    finally:
        # Ensure connection pool closed properly, even if _run had an issue
        # This might run into "Event loop is closed" if _run already closed it or failed early
        try:
            # Check if api instance was successfully created and has a client to close
            if "api" in locals() and hasattr(api, "_client") and api._client and not api._client.is_closed:
                asyncio.run(api.close())
        except RuntimeError as e:
            if "Event loop is closed" not in str(e) and "cannot schedule new futures after shutdown" not in str(e):
                print(f"Note: Error during final API client close: {e}", file=sys.stderr)
            pass


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    # To run this CLI directly:
    # 1. Ensure your project root is in PYTHONPATH or run as a module:
    #    `python -m app.cli chat`
    # 2. If running `python app/cli.py` directly, you might need to add
    #    the project root to sys.path at the top of this file (currently removed for linters).
    cli()
