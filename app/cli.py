#!/usr/bin/env python3
# app/cli.py
"""
Command-line interface for Dear Future Me.

• --demo        : run two canned messages
• --offline     : force stubbed responses (no network)
The script also auto-falls back to offline mode if no real OPENAI_API_KEY is found.
"""

import argparse
import asyncio
import os
import sys
import warnings

from dotenv import load_dotenv

# suppress LangChain deprecation noise
warnings.filterwarnings("ignore")

# so we can do `python app/cli.py` from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

load_dotenv()

# ANSI color escapes
CLIENT_PREFIX = "\033[94m🧑 Client:\033[0m"
SYSTEM_PREFIX = "\033[92m🤖 System:\033[0m"


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="CLI for Dear Future Me")
    p.add_argument("--demo", action="store_true", help="Run demo conversation")
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use stubbed replies (no OpenAI, no network)",
    )
    return p.parse_args()


def _get_orchestrator(offline: bool):
    if offline:
        # lightweight stub that just apologizes
        class _Dummy:
            async def answer(self, q: str) -> dict:
                return {"query": q, "result": f"Echo: {q}"}

        return _Dummy()

    from app.api.orchestrator import Orchestrator

    return Orchestrator()


async def _run_demo(orch) -> None:
    msgs = [
        "Hello, I'm feeling a bit anxious today.",
        "Can you help me understand why?",
    ]
    for m in msgs:
        # Client message
        print(f"{CLIENT_PREFIX} {m}\n")

        try:
            resp = await orch.answer(m)
        except Exception as e:
            print(f"⚠️  LLM error ({e}). Falling back to offline stub.\n")
            orch = _get_orchestrator(offline=True)
            resp = await orch.answer(m)

        # If the orchestrator returned a dict with 'result', unwrap it
        text = resp.get("result") if isinstance(resp, dict) else resp
        print(f"{SYSTEM_PREFIX} {text}\n")


def main() -> None:
    args = _parse_args()
    if args.demo:
        offline = args.offline or not os.getenv("OPENAI_API_KEY")
        if offline:
            warnings.warn("Running demo in OFFLINE mode (no OpenAI).", RuntimeWarning)
        asyncio.run(_run_demo(_get_orchestrator(offline)))
    else:
        print("No --demo flag provided. Nothing to do.")


if __name__ == "__main__":
    main()
