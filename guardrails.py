"""Reliability guardrails for the PawPal+ assistant.

Three checkpoints wrap the AI agent:

1. check_input()      - before the model sees a request: rejects empty or
                         oversized input and prompt-injection attempts, and
                         routes emergencies straight to a fixed vet/poison
                         control message instead of an AI-generated answer.
2. validate_task_args() - before a tool changes the schedule: the model's
                         proposed task is checked against the same rules as
                         the UI form. Errors go back to the model so it can
                         correct itself (a self-check loop).
3. check_output()     - before the answer reaches the user: flags specific
                         medication doses and care advice given without a
                         care-guide citation.

All checks are plain Python, so they behave the same every time and are
covered by unit tests and the evaluation script.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pawpal_system import FREQUENCY_DAYS, PRIORITY_VALUES, Owner, time_to_minutes

MAX_INPUT_CHARS = 1000
MAX_TASK_MINUTES = 240

EMERGENCY_PATTERNS = [
    r"\b(ate|eaten|swallowed|chewed|licked|got into)\b.*\b(chocolate|grapes?|raisins?|xylitol|onions?|garlic|lil(y|ies)|antifreeze|rat poison|ibuprofen|advil|tylenol|acetaminophen|medication|pills?)\b",
    r"\bpoison(ed|ing)?\b",
    r"\b(seizure|seizing|convuls\w*)\b",
    r"\b(not|can'?t|cannot|isn'?t|trouble|difficulty) breath\w*",
    r"\b(collapsed?|unconscious|unresponsive)\b",
    r"\b(bleeding (heavily|a lot|won'?t stop)|heavy bleeding)\b",
    r"\bhit by a car\b",
]

EMERGENCY_MESSAGE = (
    "This sounds like it could be an emergency, so PawPal+ won't try to answer it. "
    "Please contact your veterinarian or an emergency animal hospital right away. "
    "For a possible poisoning you can also call the ASPCA Animal Poison Control "
    "Center at (888) 426-4435 (24/7; a fee may apply)."
)

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules|prompts?)",
    r"disregard (your|the) (instructions|rules|system prompt)",
    r"(reveal|show|print) (me )?(your|the) (system prompt|instructions)",
    r"you are now (?!going)",
    r"\bjailbreak\b",
]

DOSE_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s?(mg|milligrams?|ml|milliliters?|mcg|cc|tablets?)\b(\s?(per|/)\s?(kg|lb|pound))?",
    re.IGNORECASE,
)

DOSE_NOTE = (
    "Safety note: PawPal+ can't confirm medication doses. "
    "Only give the dose your veterinarian prescribed."
)


@dataclass
class InputCheck:
    """Result of check_input(). If allowed is False, reply with message instead of calling the model."""

    allowed: bool
    category: str  # "ok", "empty", "too_long", "injection", "emergency"
    message: str = ""


@dataclass
class OutputCheck:
    """Result of check_output(): the (possibly amended) answer plus any flags raised."""

    text: str
    flags: list[str] = field(default_factory=list)


def check_input(text: str) -> InputCheck:
    """Screen a user request before it is sent to the model."""
    stripped = (text or "").strip()
    if not stripped:
        return InputCheck(False, "empty", "Please type a question or request.")
    if len(stripped) > MAX_INPUT_CHARS:
        return InputCheck(
            False, "too_long", f"Please keep requests under {MAX_INPUT_CHARS} characters."
        )
    lowered = stripped.lower()
    # Emergencies are checked first: safety beats everything else.
    if any(re.search(p, lowered) for p in EMERGENCY_PATTERNS):
        return InputCheck(False, "emergency", EMERGENCY_MESSAGE)
    if any(re.search(p, lowered) for p in INJECTION_PATTERNS):
        return InputCheck(
            False,
            "injection",
            "PawPal+ can only help with pet care and your schedule. Please rephrase your request.",
        )
    return InputCheck(True, "ok")


def validate_task_args(args: dict, owner: Owner) -> list[str]:
    """Check a task the model wants to add. Returns a list of problems (empty means valid).

    These are the same rules the Streamlit form enforces, so the AI can't
    create a task a person couldn't.
    """
    errors = []
    pet_name = str(args.get("pet_name", "")).strip()
    if owner.get_pet(pet_name) is None:
        known = ", ".join(p.name for p in owner.pets) or "none"
        errors.append(f"Unknown pet '{pet_name}'. Known pets: {known}.")

    if not str(args.get("description", "")).strip():
        errors.append("description must not be empty.")

    duration = args.get("duration_minutes")
    if not isinstance(duration, int) or isinstance(duration, bool) or not 1 <= duration <= MAX_TASK_MINUTES:
        errors.append(f"duration_minutes must be a whole number from 1 to {MAX_TASK_MINUTES}.")

    if str(args.get("priority", "")).lower() not in PRIORITY_VALUES:
        errors.append(f"priority must be one of {list(PRIORITY_VALUES)}.")

    if str(args.get("frequency", "")).lower() not in FREQUENCY_DAYS:
        errors.append(f"frequency must be one of {list(FREQUENCY_DAYS)}.")

    time = str(args.get("time", "")).strip()
    if time and time_to_minutes(time) is None:
        errors.append("time must be HH:MM on a 24-hour clock (e.g. 07:30), or an empty string.")
    return errors


def check_output(text: str, used_care_guide: bool, cited: bool) -> OutputCheck:
    """Review the agent's final answer before showing it.

    Args:
        text: The model's final answer.
        used_care_guide: Whether the agent called search_care_guide this turn.
        cited: Whether the answer contains a [source.md > Section] citation.
    """
    flags = []
    if DOSE_PATTERN.search(text):
        flags.append("dose_mentioned")
        text = f"{text}\n\n{DOSE_NOTE}"
    if used_care_guide and not cited:
        flags.append("uncited_advice")
    return OutputCheck(text, flags)


CITATION_PATTERN = re.compile(r"\[[\w\-]+\.md\s*>\s*[^\]]+\]")


def has_citation(text: str) -> bool:
    """True if the text cites a care-guide section like [dog_care.md > Feeding schedule]."""
    return bool(CITATION_PATTERN.search(text))
