#!/usr/bin/env python3
"""
Command-line interface for Dear Future Me.

Usage:
  --demo    Run the demo conversation sequence
"""

import argparse
import asyncio
import os
import sys

# Ensure project root is on the Python path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from app.api.orchestrator import Orchestrator


def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments. Returns an argparse.Namespace.
    """
    parser = argparse.ArgumentParser(description="CLI for Dear Future Me application")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the demo conversation sequence",
    )
    return parser.parse_args()


async def run_demo_sequence() -> None:
    """
    Run a simple demonstration sequence in the CLI,
    showing a client-system conversation.
    """
    orch = Orchestrator()
    demo_messages = [
        "Hello, I'm feeling a bit anxious today.",
        "Can you help me understand why?",
    ]
    for msg in demo_messages:
        print(f"Client: {msg}")
        reply = await orch.answer(msg)
        print(f"System: {reply}")


def main() -> None:
    """
    Entry point for the CLI.
    """
    args = parse_args()
    if args.demo:
        asyncio.run(run_demo_sequence())
    else:
        print("No demo flag detected. Use --demo to run the demo sequence.")


if __name__ == "__main__":
    main()
