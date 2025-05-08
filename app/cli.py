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

# --------------------------------------------------------------------------- #
# Environment & constants
# --------------------------------------------------------------------------- #

load_dotenv()  # .env in project root

API_URL = os.getenv("DFM_API_URL", "http://localhost:8000")
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
_DEFAULT_PWD = os.getenv("DFM_DEMO_PASSWORD", "secret")


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

    async def login(self, email: str, password: str):  #  -> str: # error: Incompatible return value type
        form = {"username": email, "password": password}
        r = await self._post("/auth/login", data=form)
        self._token = r.json()["access_token"]
        return self._token

    async def register_demo_user(self) -> str:
        """Registers a random user & immediately logs in."""
        email = f"demo_{uuid.uuid4()}@example.com"
        pwd = _DEFAULT_PWD
        try:
            # Registration may fail (if DEMO_MODE disables auth), so ignore errors.
            await self._post("/auth/register", json={"email": email, "password": pwd})
        except httpx.HTTPStatusError:
            pass
        return await self.login(email, pwd)

    # ----------------------------- business ---------------------------------

    async def chat(self, message: str) -> str:
        r = await self._post("/chat/text", json={"message": message})
        data = r.json()
        # if "answer" not in data:
        #     # Backend returned something unexpected – surface to user & dev log.
        #     raise RuntimeError(f"Unexpected response payload: {data}")
        # return data["answer"]
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
        token: Optional[str] = None
        if not DEMO_MODE:
            token = await api.register_demo_user()
        banner = f"[bold green]Logged in as {token}[/bold green]\n" if token else ""
        console.print(banner + "[bold]Dear-Future-Me interactive chat[/bold]")
        console.print("Type 'exit' to quit.\n")

        # ------------------------------------------------------------------ loop
        while True:
            try:
                # query = Prompt.ask(Text("you:", style="bold bright_white")).strip()
                query = console.input("[bold cyan]you:[/bold cyan] ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[bold]Bye![/bold]")
                break

            if query.lower() in {"exit", "quit"}:
                break

            try:
                answer = await api.chat(query)
            except Exception as ex:  # noqa: BLE001
                console.print("[bold red]Oops! Something went wrong on the server side.[/bold red]")
                console.print("(Details logged to stderr)")
                print("----- TRACEBACK -----", file=sys.stderr)
                import traceback

                traceback.print_exception(ex, file=sys.stderr)
                break

            console.print(Text("ai:", style="bold cyan"), answer)

    try:
        asyncio.run(_run())
    finally:
        # Ensure connection pool closed properly
        try:
            asyncio.run(api.close())
        except RuntimeError:
            pass


# --------------------------------------------------------------------------- #
# Entry-point
# --------------------------------------------------------------------------- #

if __name__ == "__main__":  # pragma: no cover
    cli()
