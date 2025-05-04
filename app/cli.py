# app/cli.py
"""
Command‑line interface for Dear Future Me.

• --demo        : run two canned messages
• --offline     : force stubbed responses (no network)
The script also auto‑falls back to offline mode if a *real* OPENAI_API_KEY
is not found.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import warnings

# Add project root for `python app/cli.py`
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()


# ─── argument parsing ────────────────────────────────────────────────
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CLI for Dear Future Me")
    p.add_argument("--demo", action="store_true", help="Run demo conversation")
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use stubbed replies (no OpenAI, no network)",
    )
    return p.parse_args()


# ─── orchestrator selection ──────────────────────────────────────────
def _get_orchestrator(offline: bool):
    if offline:
        # lightweight stub that just echoes
        class _Dummy:
            async def answer(self, q: str) -> str:
                return f"Echo: {q}"

        return _Dummy()

    # real orchestrator (may raise if key invalid)
    from app.api.orchestrator import Orchestrator

    return Orchestrator()


# ─── demo sequence ──────────────────────────────────────────────────
async def _run_demo(orch) -> None:
    msgs = [
        "Hello, I'm feeling a bit anxious today.",
        "Can you help me understand why?",
    ]
    for m in msgs:
        print(f"Client: {m}")
        try:
            reply = await orch.answer(m)
        except Exception as e:  # pylint: disable=broad-except
            print(f"⚠️  LLM error ({e}). Falling back to offline stub.")
            orch = _get_orchestrator(offline=True)
            reply = await orch.answer(m)
        print(f"System: {reply}")


# ─── main ────────────────────────────────────────────────────────────
def main() -> None:
    args = _parse_args()
    if args.demo:
        # Decide offline/online
        offline = (
            args.offline
            or not os.getenv("OPENAI_API_KEY")
            or os.getenv("OPENAI_API_KEY") == "test-key"
        )
        if offline:
            warnings.warn("Running demo in OFFLINE mode (no OpenAI).", RuntimeWarning)
        asyncio.run(_run_demo(_get_orchestrator(offline)))
    else:
        print("No --demo flag provided. Nothing to do.")


if __name__ == "__main__":
    main()
