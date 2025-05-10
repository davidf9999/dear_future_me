# /home/dfront/code/dear_future_me/app/cli.py
"""
app/cli.py
~~~~~~~~~~

Small helper CLI for local demo & smoke-tests.
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from typing import Any, Dict, Optional

import click
import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.text import Text

from app.core.settings import get_settings  # For typed access to settings

# --------------------------------------------------------------------------- #
# Environment & constants
# --------------------------------------------------------------------------- #

load_dotenv()
cfg = get_settings()

API_URL = os.getenv("DFM_API_URL", "http://localhost:8000")
CLIENT_DEMO_MODE = cfg.DEMO_MODE  # For CLI's decision on using demo user
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

# --------------------------------------------------------------------------- #
# Helper HTTP wrapper
# --------------------------------------------------------------------------- #


class API:
    """Thin async wrapper around the HTTP endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def _post(
        self,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        _headers = headers or {}
        if self._token:
            _headers["Authorization"] = f"Bearer {self._token}"
        resp = await self._client.post(url, json=json, data=data, headers=_headers)
        resp.raise_for_status()
        return resp

    async def login(self, email: str, password: str):
        form = {"username": email, "password": password}
        r = await self._post("/auth/login", data=form)
        self._token = r.json()["access_token"]
        return self._token

    async def setup_session_auth(self) -> Optional[str]:
        if CLIENT_DEMO_MODE:
            email = cfg.DEMO_USER_EMAIL
            password = cfg.DEMO_USER_PASSWORD
            console.print(STR["attempting_demo_user_setup"].format(email=email))
        else:
            email = f"temp_cli_user_{uuid.uuid4().hex[:8]}@example.com"
            password = "cli_temppassword"
            console.print(STR["attempting_temp_user_setup"].format(email=email))

        try:
            await self.login(email, password)
            console.print(STR["login_success"].format(email=email))
            return self._token
        except httpx.HTTPStatusError as login_err:
            if login_err.response.status_code == 400:
                console.print(
                    STR["login_failed_attempt_register"].format(email=email, status_code=login_err.response.status_code)
                )
                try:
                    user_create_payload = {
                        "email": email,
                        "password": password,
                        "first_name": "CLI",
                        "last_name": "User" if not CLIENT_DEMO_MODE else "Demo",
                    }
                    await self._post("/auth/register", json=user_create_payload)
                    console.print(STR["user_registered_logging_in"].format(email=email))
                    await self.login(email, password)
                    console.print(STR["login_success_after_register"].format(email=email))
                    return self._token
                except httpx.HTTPStatusError as reg_err:
                    console.print(
                        STR["registration_failed"].format(
                            email=email, status_code=reg_err.response.status_code, text=reg_err.response.text
                        )
                    )
                    return None
            else:
                console.print(
                    STR["login_error_other"].format(
                        email=email, status_code=login_err.response.status_code, text=login_err.response.text
                    )
                )
                return None
        except Exception as e:
            console.print(STR["unexpected_auth_error"].format(email=email, error=e))
            import traceback

            traceback.print_exc()
            return None

    async def chat(self, message: str) -> str:
        r = await self._post("/chat/text", json={"message": message})
        data = r.json()
        answer = data.get("answer") or data.get("reply")
        if answer is None:
            raise RuntimeError(f"Unexpected response payload: {data}")
        return answer

    async def close(self) -> None:
        await self._client.aclose()


console = Console()


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
    api = API(url)

    async def _run() -> None:
        try:
            token = await api.setup_session_auth()
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

        while True:
            try:
                query = console.input(STR["user_prompt"]).strip()
            except (KeyboardInterrupt, EOFError):
                console.print(STR["bye_message"])
                break

            if query.lower() in {"exit", "quit", "צא"}:  # Added Hebrew exit command
                console.print(STR["bye_message"])
                break

            if not query:
                continue

            try:
                answer = await api.chat(query)
            except httpx.HTTPStatusError as ex_http:
                console.print(
                    STR["http_error_from_server"].format(
                        status_code=ex_http.response.status_code, text=ex_http.response.text
                    )
                )
                if ex_http.response.status_code == 401:
                    console.print(STR["session_expired_error"])
            except Exception as ex:
                console.print(STR["generic_comms_error"])
                console.print(STR["details_to_stderr"])
                print("----- TRACEBACK -----", file=sys.stderr)
                import traceback

                traceback.print_exception(ex, file=sys.stderr)
                break

            console.print(Text(STR["ai_prompt"], style="bold cyan"), answer)  # Keep style for AI prompt

        await api.close()

    try:
        asyncio.run(_run())
    except RuntimeError as e:
        if "Event loop is closed" not in str(e):
            raise
    finally:
        try:
            if hasattr(api, "_client") and api._client and not api._client.is_closed:  # Check if api and _client exist
                asyncio.run(api.close())
        except RuntimeError as e:
            if "Event loop is closed" not in str(e) and "cannot schedule new futures after shutdown" not in str(e):
                print(f"Note: Error during final API client close: {e}", file=sys.stderr)
            pass


if __name__ == "__main__":
    cli()
