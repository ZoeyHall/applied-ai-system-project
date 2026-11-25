"""Command-line demo of the PawPal+ AI assistant.

Usage:
    python assistant_cli.py "How often should I trim Biscuit's nails?"
    python assistant_cli.py --demo        # runs the three example requests from the README
    python assistant_cli.py               # interactive: type requests, blank line to quit
    python assistant_cli.py --offline --demo   # no API key needed: care guide + scheduler only

Without a valid API key, the CLI switches to offline mode automatically.

Every run is appended to logs/agent_traces.md.
"""

from __future__ import annotations

import argparse

from agent import MissingCredentialsError, PawPalAgent
from pawpal_system import Owner, Pet, Task

DEMO_REQUESTS = [
    "How often should I scoop Mochi's litter box, and how many boxes do I need?",
    "Mochi needs her thyroid pill every morning at 8:00, it takes 5 minutes. Add it, then plan my day.",
    "Add a 20 minute evening walk for Biscuit at 25:00.",
]

# Requests that offline mode can handle (no free-form task creation without the AI).
DEMO_OFFLINE_REQUESTS = [
    "How often should I scoop Mochi's litter box, and how many boxes do I need?",
    "How often should I trim Biscuit's nails?",
    "What does my day look like?",
    "Can I give Mochi Tylenol for pain?",
    "Biscuit ate grapes",
]


def build_demo_owner() -> Owner:
    """A small household used by the CLI demo and the evaluation script."""
    owner = Owner(name="Jordan", available_minutes=90)
    biscuit = Pet(name="Biscuit", species="dog", age=4)
    mochi = Pet(name="Mochi", species="cat", age=2)
    owner.add_pet(biscuit)
    owner.add_pet(mochi)
    biscuit.add_task(Task("Morning walk", 30, "high", time="07:30"))
    biscuit.add_task(Task("Breakfast", 10, "high", time="08:00"))
    mochi.add_task(Task("Breakfast", 10, "high", time="07:30"))
    mochi.add_task(Task("Clean litter box", 10, "medium"))
    mochi.add_task(Task("Laser pointer play", 25, "low", time="20:00"))
    return owner


def print_result(result) -> None:
    print(f"\nYou: {result.request}")
    if result.blocked:
        print(f"[input guardrail: {result.blocked}]")
    else:
        tools = ", ".join(result.tools_used) or "none"
        print(f"[tools used: {tools}]")
    if result.flags:
        print(f"[output flags: {', '.join(result.flags)}]")
    print(f"PawPal+: {result.answer}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the PawPal+ AI assistant.")
    parser.add_argument("request", nargs="?", help="A question or scheduling request.")
    parser.add_argument("--demo", action="store_true", help="Run the example requests.")
    parser.add_argument(
        "--offline", action="store_true", help="Don't call Claude: use the care guide and scheduler only."
    )
    args = parser.parse_args()

    agent = PawPalAgent(build_demo_owner())
    offline = args.offline

    def ask(request: str) -> None:
        """Answer one request with Claude, falling back to offline mode if there's no valid key."""
        nonlocal offline
        if not offline:
            try:
                print_result(agent.run(request))
                return
            except MissingCredentialsError as exc:
                print(f"\n{exc}\nSwitching to offline mode (care guide + scheduler, no AI).")
                offline = True
        print_result(agent.run_offline(request))

    if args.demo:
        # Both demo lists start with the same care question, so ask it first and
        # then continue with whichever list matches the mode we ended up in.
        ask(DEMO_REQUESTS[0])
        for request in (DEMO_OFFLINE_REQUESTS if offline else DEMO_REQUESTS)[1:]:
            ask(request)
    elif args.request:
        ask(args.request)
    else:
        print("PawPal+ assistant (household: Jordan, Biscuit the dog, Mochi the cat). Blank line quits.")
        while (request := input("\nYou: ").strip()):
            ask(request)
    print("\nTrace saved to logs/agent_traces.md")


if __name__ == "__main__":
    main()
