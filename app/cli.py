"""
app/cli.py
~~~~~~~~~~

Small helper CLI for local demo & smoke-tests.

Highlights
----------
* Auto-loads environment variables from `.env` (python-dotenv).
* Registers a throw-away *demo* user (one per run) when AUTH is enabled.
* Pretty TTY chat with **rich** colours.
* Fails loudly (no “Echo” fall-back) if the backend doesn’t return
  the expected JSON shape.

Dependencies: click, httpx, rich, python-dotenv
These are already in requirements.txt — add them if you trimmed the list.
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

load_dotenv()  # .env in project root
cfg = get_settings()  # Load settings once

API_URL = os.getenv("DFM_API_URL", "http://localhost:8000")  # Can keep this for overriding API_URL via env
# CLIENT_DEMO_MODE for CLI now primarily dictates if it tries to use the .env demo user
# This uses the DEMO_MODE from the .env file that the CLI itself reads.
CLIENT_DEMO_MODE = cfg.DEMO_MODE


# --------------------------------------------------------------------------- #
# Helper HTTP wrapper
# --------------------------------------------------------------------------- #


class API:
    """Thin async wrapper around the HTTP endpoints."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._token: Optional[str] = None
        self._client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    # ----------------------------- low-level --------------------------------

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

    # ----------------------------- auth -------------------------------------

    async def login(self, email: str, password: str):
        form = {"username": email, "password": password}
        r = await self._post("/auth/login", data=form)
        self._token = r.json()["access_token"]
        return self._token

    async def setup_session_auth(self) -> Optional[str]:
        """
        Handles authentication for the CLI session.
        If CLIENT_DEMO_MODE is true, attempts to register/login the predefined demo user from settings.
        Otherwise, registers and logs in a new random temporary user.
        Returns the token or None if auth fails.
        """
        if CLIENT_DEMO_MODE:
            email = cfg.DEMO_USER_EMAIL
            password = cfg.DEMO_USER_PASSWORD
            console.print(f"[dim]CLIENT_DEMO_MODE is True. Attempting to use predefined demo user: {email}...[/dim]")
        else:
            email = f"temp_cli_user_{uuid.uuid4().hex[:8]}@example.com"
            password = "cli_temppassword"
            console.print(
                f"[dim]CLIENT_DEMO_MODE is False. Attempting to register/login temporary user: {email}...[/dim]"
            )

        try:
            # Try to login first
            await self.login(email, password)
            console.print(f"[green]Successfully logged in as {email}[/green]")
            return self._token
        except httpx.HTTPStatusError as login_err:
            # FastAPI-Users returns 400 for bad credentials / user not found during login
            if login_err.response.status_code == 400:
                console.print(
                    f"[yellow]Login failed for {email} (status {login_err.response.status_code}). Attempting to register...[/yellow]"
                )
                try:
                    # Provide some default names for registration
                    user_create_payload = {
                        "email": email,
                        "password": password,
                        "first_name": "CLI",
                        "last_name": "User" if not CLIENT_DEMO_MODE else "Demo",
                    }
                    await self._post("/auth/register", json=user_create_payload)
                    console.print(f"[green]User {email} registered. Logging in...[/green]")
                    await self.login(email, password)  # Try login again after registration
                    console.print(f"[green]Successfully logged in as {email} after registration[/green]")
                    return self._token
                except httpx.HTTPStatusError as reg_err:
                    console.print(
                        f"[red]Registration for {email} failed (status {reg_err.response.status_code}): {reg_err.response.text}[/red]"
                    )
                    return None
            else:  # Other login errors
                console.print(
                    f"[red]Login error for {email} (status {login_err.response.status_code}): {login_err.response.text}[/red]"
                )
                return None
        except Exception as e:
            console.print(f"[red]Unexpected error during auth setup for {email}: {e}[/red]")
            import traceback

            traceback.print_exc()
            return None

    # ----------------------------- business ---------------------------------

    async def chat(self, message: str) -> str:
        r = await self._post("/chat/text", json={"message": message})
        data = r.json()
        answer = data.get("answer") or data.get("reply")
        if answer is None:
            raise RuntimeError(f"Unexpected response payload: {data}")
        return answer

    async def close(self) -> None:
        await self._client.aclose()


# --------------------------------------------------------------------------- #
# CLI definition (click)
# --------------------------------------------------------------------------- #

console = Console()


@click.group()
def cli() -> None:  # pragma: no cover
    """Dear-Future-Me utility CLI."""
    pass


@cli.command(help="Interactive chat with the running API server.")
@click.option(
    "--url",
    default=API_URL,
    show_default=True,
    help="Base URL of the FastAPI server.",
)
def chat(url: str) -> None:  # pragma: no cover
    """Start an interactive chat session."""
    api = API(url)

    async def _run() -> None:
        # ------------------------------------------------------------------ auth
        try:
            token = await api.setup_session_auth()
            if not token:
                console.print("[bold red]Authentication failed. Cannot start chat session. Exiting.[/bold red]")
                console.print(
                    "[bold yellow]Please check server logs and ensure the server is running and accessible.[/bold yellow]"
                )
                if CLIENT_DEMO_MODE:
                    console.print(
                        f"[bold yellow]Ensure DEMO_USER_EMAIL ({cfg.DEMO_USER_EMAIL}) and DEMO_USER_PASSWORD are correctly set in your .env file if using CLIENT_DEMO_MODE.[/bold yellow]"
                    )
                return

            user_email_for_banner = (
                cfg.DEMO_USER_EMAIL if CLIENT_DEMO_MODE and api._token else "authenticated user"
            )  # Fallback if token somehow not set
            banner = f"[bold green]Authenticated as {user_email_for_banner}[/bold green]\n"
        except Exception as e:
            console.print(f"[bold red]Critical error during authentication setup: {e}[/bold red]")
            banner = "[bold red]Could not authenticate. Chat session cannot start.[/bold red]\n"
            console.print(banner)
            return

        console.print(banner + "[bold]Dear-Future-Me interactive chat[/bold]")
        console.print("Type 'exit' to quit.\n")

        # ------------------------------------------------------------------ loop
        while True:
            try:
                query = console.input("[bold cyan]you:[/bold cyan] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold]Bye![/bold]")
                break

            if query.lower() in {"exit", "quit"}:
                break

            if not query:  # Skip empty input
                continue

            try:
                answer = await api.chat(query)
            except httpx.HTTPStatusError as ex_http:
                console.print(
                    f"[bold red]Oops! HTTP error from server: {ex_http.response.status_code} - {ex_http.response.text}[/bold red]"
                )
                if ex_http.response.status_code == 401:  # Unauthorized
                    console.print(
                        "[bold yellow]Your session might have expired or token is invalid. Try restarting the CLI.[/bold yellow]"
                    )
                # For other HTTP errors, we might want to break or allow retry
                # break
            except Exception as ex:  # noqa: BLE001
                console.print(
                    "[bold red]Oops! Something went wrong on the server side or during communication.[/bold red]"
                )
                console.print("(Details logged to stderr)")
                print("----- TRACEBACK -----", file=sys.stderr)
                import traceback

                traceback.print_exception(ex, file=sys.stderr)
                break  # Break on unexpected errors

            console.print(Text("ai:", style="bold cyan"), answer)

        await api.close()

    try:
        asyncio.run(_run())
    except RuntimeError as e:  # Catch asyncio's "Event loop is closed" if _run() itself raises early
        if "Event loop is closed" not in str(e):
            raise  # Re-raise if it's not the specific loop closure error
    finally:
        # Ensure connection pool closed properly, even if _run had an issue
        # This might run into "Event loop is closed" if _run already closed it or failed early
        try:
            if not api._client.is_closed:
                asyncio.run(api.close())
        except RuntimeError as e:
            if "Event loop is closed" not in str(e) and "cannot schedule new futures after shutdown" not in str(e):
                # Log or print if it's a different runtime error during close
                print(f"Note: Error during final API client close: {e}", file=sys.stderr)
            pass


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    cli()
