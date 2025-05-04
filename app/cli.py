# app/cli.py
import argparse
import asyncio
from app.api.orchestrator import Orchestrator


async def run_interactive():
    """
    Interactive CLI: reads user input and prints system replies.
    """
    orch = Orchestrator()
    print("=== Dear Future Me CLI Demo ===")
    print("(Type 'exit' to quit)")
    while True:
        user_input = input("Client: ")
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        # Get orchestrator answer
        try:
            reply = await orch.answer(user_input)
        except Exception as e:
            reply = f"[Error generating reply: {e}]"
        print(f"System: {reply}\n")


def run_demo_sequence(sequence):
    """
    Given a list of (speaker, message) pairs, simulate the conversation and return list of responses.
    """
    orch = Orchestrator()
    replies = []
    for speaker, msg in sequence:
        # we only process client messages
        if speaker.lower() == "client":
            # orchestrator.answer might be async
            coro = orch.answer(msg)
            if asyncio.iscoroutine(coro):
                resp = asyncio.get_event_loop().run_until_complete(coro)
            else:
                resp = coro
            replies.append(("System", resp))
    return replies


def main():
    parser = argparse.ArgumentParser(description="CLI demo for Dear Future Me")
    parser.add_argument(
        "--demo", action="store_true", help="Run a scripted demo conversation"
    )
    args = parser.parse_args()

    if args.demo:
        # A simple fake conversation
        script = [
            ("Client", "I feel anxious about my upcoming meeting."),
            ("Client", "I’m not sure how to prepare."),
        ]
        responses = run_demo_sequence(script)
        for (speaker, msg), (_, reply) in zip(script, responses):
            print(f"{speaker}: {msg}")
            print(f"System: {reply}\n")
    else:
        # interactive mode
        try:
            asyncio.run(run_interactive())
        except KeyboardInterrupt:
            print("\nInterrupted. Goodbye!")


if __name__ == "__main__":
    main()
