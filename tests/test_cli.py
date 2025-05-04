# File: app/cli.py
import argparse
import asyncio

from app.api.orchestrator import Orchestrator


def parse_args():
    """
    Parse command line arguments. Returns an argparse.Namespace.
    """
    parser = argparse.ArgumentParser(
        description="CLI for Dear Future Me application"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the demo conversation sequence",
    )
    return parser.parse_args()


async def run_demo_sequence():
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


def main():
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