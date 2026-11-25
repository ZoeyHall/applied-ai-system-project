"""PawPal+ AI assistant: a Claude tool-use agent wired into the scheduler.

The owner types a plain-language request ("Mochi needs her pill every morning
at 8, then plan my day"). The agent works in steps:

    input guardrail -> Claude plans -> calls tools -> sees results -> ...
    -> final answer -> output guardrail -> answer + saved trace

Tools give Claude read access to the household, retrieval over the care guide
(RAG), and write access to the schedule through validated add_task calls. The
real Scheduler from pawpal_system.py builds the plan, so the AI changes the
same Owner/Pet/Task objects the Streamlit UI shows.

Every step (Claude's reasoning summary, each tool call, guardrail verdicts and
tool results) is recorded and appended to logs/agent_traces.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from guardrails import check_input, check_output, has_citation, validate_task_args
from pawpal_system import Owner, Scheduler, Task, format_minutes, time_to_minutes
from retriever import CareGuideRetriever

MODEL = "claude-opus-5-5"
MAX_STEPS = 8
TRACE_PATH = Path(__file__).parent / "logs" / "agent_traces.md"

SYSTEM_PROMPT = """You are PawPal+, a pet care planning assistant inside a scheduling app.

You help one owner manage care tasks for their pets and answer pet care questions.
Use the tools to look at the household before acting; never invent pets or tasks.

Scheduling:
- To add a task, call add_task. If it returns an error, fix the arguments and try again,
  or ask the owner if the request was unclear. Don't add the same task twice.
- Times use a 24-hour clock (HH:MM). Use an empty string when the owner gives no time.
- Pick a priority that matches the care guide: medication and feeding are high,
  hygiene is medium, enrichment and grooming are usually low or medium.
- When the owner asks for their day or schedule, call generate_plan and summarize it,
  including skipped tasks and conflicts.

Care questions:
- Answer from search_care_guide results, and cite each fact with its source in brackets
  exactly as given, e.g. [cat_care.md > Litter box care].
- If the guide has nothing relevant, say so and suggest asking a veterinarian.
- Never give medication doses; tell the owner to follow their vet's instructions.

Keep answers short and friendly: a few sentences or a short list."""

TOOLS = [
    {
        "name": "list_pets",
        "description": "List the owner's pets (name, species, age) and how many minutes the owner has today.",
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "list_tasks",
        "description": "List care tasks, optionally for one pet and by status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string", "description": "A pet's name, or an empty string for all pets."},
                "status": {"type": "string", "enum": ["pending", "done", "all"]},
            },
            "required": ["pet_name", "status"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "search_care_guide",
        "description": (
            "Search the PawPal+ pet care guide (feeding, exercise, grooming, litter, enrichment, "
            "medication safety, toxic foods, routines). Returns cited sections."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords or a question."},
                "species": {"type": "string", "enum": ["dog", "cat", "any"]},
            },
            "required": ["query", "species"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "add_task",
        "description": "Add a care task for one pet. The task is validated before it is saved.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pet_name": {"type": "string"},
                "description": {"type": "string", "description": "Short task name, e.g. 'Evening walk'."},
                "duration_minutes": {"type": "integer"},
                "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                "time": {"type": "string", "description": "Start time as HH:MM (24-hour), or '' for any time."},
                "frequency": {"type": "string", "enum": ["daily", "weekly", "once"]},
            },
            "required": ["pet_name", "description", "duration_minutes", "priority", "time", "frequency"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "generate_plan",
        "description": (
            "Build today's schedule with the PawPal+ scheduler: picks tasks by priority that fit the "
            "owner's available minutes, orders them by time, and reports skipped tasks and conflicts."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
]


@dataclass
class AgentResult:
    """What one run of the agent produced."""

    request: str
    answer: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    blocked: str = ""  # input-guardrail category if the model was never called
    tools_used: list[str] = field(default_factory=list)
    tasks_added: list[str] = field(default_factory=list)


class PawPalAgent:
    """Runs Claude in a tool-use loop over one Owner's pets and tasks."""

    def __init__(
        self,
        owner: Owner,
        client: Any = None,
        retriever: CareGuideRetriever | None = None,
        model: str = MODEL,
        max_steps: int = MAX_STEPS,
        trace_path: Path | None = TRACE_PATH,
    ) -> None:
        self.owner = owner
        self.scheduler = Scheduler(owner)
        self.retriever = retriever or CareGuideRetriever()
        self.model = model
        self.max_steps = max_steps
        self.trace_path = trace_path
        self._client = client

    @property
    def client(self) -> Any:
        # Created lazily so guardrail-only runs and tests work without the SDK or a key.
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    # ---- tools -------------------------------------------------------------

    def _tool_list_pets(self, args: dict) -> str:
        pets = [{"name": p.name, "species": p.species, "age": p.age} for p in self.owner.pets]
        return json.dumps(
            {"owner": self.owner.name, "available_minutes": self.owner.available_minutes, "pets": pets}
        )

    def _tool_list_tasks(self, args: dict) -> str:
        completed = {"pending": False, "done": True}.get(args.get("status", "all"))
        tasks = self.scheduler.filter_tasks(pet_name=args.get("pet_name") or None, completed=completed)
        rows = [
            {
                "pet": t.pet_name,
                "description": t.description,
                "minutes": t.duration_minutes,
                "priority": t.priority,
                "time": t.time or "any",
                "frequency": t.frequency,
                "due": t.due_date.isoformat(),
                "done": t.completed,
            }
            for t in self.scheduler.sort_by_time(tasks)
        ]
        return json.dumps(rows) if rows else "No matching tasks."

    def _tool_search_care_guide(self, args: dict) -> str:
        species = args.get("species")
        results = self.retriever.search(args.get("query", ""), species=None if species == "any" else species)
        return self.retriever.format_results(results)

    def _tool_add_task(self, args: dict) -> str:
        errors = validate_task_args(args, self.owner)
        if errors:
            raise ToolInputError("Task not added. " + " ".join(errors))

        pet = self.owner.get_pet(args["pet_name"].strip())
        description = args["description"].strip()
        duplicate = any(
            t.description.lower() == description.lower() and not t.completed for t in pet.tasks
        )
        if duplicate:
            raise ToolInputError(f"{pet.name} already has a pending task named '{description}'. Not added again.")

        start = time_to_minutes(args["time"].strip()) if args["time"].strip() else None
        task = Task(
            description=description,
            duration_minutes=args["duration_minutes"],
            priority=args["priority"],
            time=format_minutes(start) if start is not None else "",
            frequency=args["frequency"],
        )
        pet.add_task(task)
        conflicts = [
            w
            for w in self.scheduler.detect_conflicts(self.scheduler.get_pending_tasks())
            if f"'{task.description}'" in w
        ]
        message = f"Added '{task.description}' for {pet.name} ({task.duration_minutes} min, {task.priority}, {task.time or 'any time'}, {task.frequency})."
        if conflicts:
            message += " Conflicts: " + " ".join(conflicts)
        return message

    def _tool_generate_plan(self, args: dict) -> str:
        self.scheduler.generate_plan()
        return self.scheduler.explain_plan()

    def execute_tool(self, name: str, args: dict) -> tuple[str, bool]:
        """Run one tool. Returns (result text, is_error)."""
        handler = getattr(self, f"_tool_{name}", None)
        if handler is None:
            return f"Unknown tool '{name}'.", True
        try:
            return handler(args), False
        except ToolInputError as exc:
            return str(exc), True
        except (ValueError, KeyError, TypeError) as exc:
            return f"Tool error: {exc}", True

    # ---- main loop ---------------------------------------------------------

    def run(self, request: str) -> AgentResult:
        """Handle one owner request end to end and return the answer with its trace."""
        result = AgentResult(request=request, answer="")

        verdict = check_input(request)
        result.steps.append({"kind": "input_guardrail", "category": verdict.category})
        if not verdict.allowed:
            result.answer, result.blocked = verdict.message, verdict.category
            self._save_trace(result)
            return result

        messages: list[dict[str, Any]] = [{"role": "user", "content": request.strip()}]
        used_guide = False
        final_text = ""

        for step in range(1, self.max_steps + 1):
            response = self._call_model(messages)

            thinking = [b.thinking for b in response.content if b.type == "thinking" and b.thinking]
            text = "\n".join(b.text for b in response.content if b.type == "text").strip()
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            result.steps.append(
                {
                    "kind": "model",
                    "step": step,
                    "stop_reason": response.stop_reason,
                    "thinking": thinking,
                    "text": text,
                    "tool_calls": [{"name": b.name, "input": b.input} for b in tool_calls],
                }
            )

            if response.stop_reason == "refusal":
                final_text = "Sorry, I can't help with that request. Please ask a pet care or scheduling question."
                break
            if response.stop_reason == "max_tokens":
                final_text = text or "Sorry, my answer was cut off. Please try a shorter request."
                break

            messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason != "tool_use" or not tool_calls:
                final_text = text
                break

            tool_results = []
            for call in tool_calls:
                output, is_error = self.execute_tool(call.name, call.input)
                result.tools_used.append(call.name)
                if call.name == "search_care_guide":
                    used_guide = True
                if call.name == "add_task" and not is_error:
                    result.tasks_added.append(call.input.get("description", ""))
                result.steps.append(
                    {"kind": "tool", "name": call.name, "is_error": is_error, "output": output}
                )
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": call.id, "content": output, "is_error": is_error}
                )
            # All results for one turn go back in a single user message.
            messages.append({"role": "user", "content": tool_results})
        else:
            final_text = "I couldn't finish that within the step limit. Try breaking the request into smaller parts."
            result.flags.append("step_limit")

        checked = check_output(final_text, used_care_guide=used_guide, cited=has_citation(final_text))
        result.answer = checked.text
        result.flags.extend(checked.flags)
        result.steps.append({"kind": "output_guardrail", "flags": checked.flags})
        self._save_trace(result)
        return result

    def run_offline(self, request: str) -> AgentResult:
        """Answer without Claude, for when no API key is available.

        Uses the same guardrails, retriever and scheduler as the AI path, so
        the app still works (and can be graded) without a key. It can't
        understand free-form scheduling requests; it only builds the plan or
        returns the best-matching care-guide sections with citations.
        """
        result = AgentResult(request=request, answer="")
        verdict = check_input(request)
        result.steps.append({"kind": "input_guardrail", "category": verdict.category})
        if not verdict.allowed:
            result.answer, result.blocked = verdict.message, verdict.category
            self._save_trace(result)
            return result

        result.steps.append({"kind": "offline"})
        lowered = request.lower()
        wants_add = lowered.startswith("add ") or " add " in f" {lowered} "
        add_note = "Adding tasks from plain language needs the AI assistant (an API key); please use the task form instead."
        if any(word in lowered for word in ("plan", "schedule", "my day")):
            output = self._tool_generate_plan({})
            result.tools_used.append("generate_plan")
            result.steps.append({"kind": "tool", "name": "generate_plan", "is_error": False, "output": output})
            result.answer = f"[offline mode] Here is today's plan from the PawPal+ scheduler:\n{output}"
            if wants_add:
                result.answer += f"\n({add_note})"
        elif wants_add:
            result.answer = f"[offline mode] {add_note}"
        else:
            species = next((p.species for p in self.owner.pets if p.name.lower() in lowered), None)
            results = self.retriever.search(request, species=species, k=2)
            result.tools_used.append("search_care_guide")
            output = self.retriever.format_results(results)
            result.steps.append({"kind": "tool", "name": "search_care_guide", "is_error": False, "output": output})
            if results:
                lines = ["[offline mode] The most relevant care-guide sections:"]
                for chunk, _ in results:
                    lines.append(f"- [{chunk.citation}] {chunk.text}")
                result.answer = "\n".join(lines)
            else:
                result.answer = "[offline mode] The care guide doesn't cover that. Please ask your veterinarian."

        checked = check_output(result.answer, used_care_guide=False, cited=True)
        result.answer = checked.text
        result.flags.extend(checked.flags)
        result.steps.append({"kind": "output_guardrail", "flags": checked.flags})
        self._save_trace(result)
        return result

    def _call_model(self, messages: list[dict[str, Any]]) -> Any:
        """Send the conversation so far to Claude and return its next message."""
        try:
            return self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
                thinking={"type": "adaptive", "display": "summarized"},
                output_config={"effort": "medium"},
                # If a safety classifier declines, the API retries on a fallback model.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except TypeError as exc:
            # The SDK raises TypeError when no API key or login is configured.
            if "authentication" in str(exc).lower():
                raise MissingCredentialsError(
                    "No Anthropic API key found. Set the ANTHROPIC_API_KEY environment variable."
                ) from exc
            raise
        except Exception as exc:
            if type(exc).__name__ == "AuthenticationError":
                raise MissingCredentialsError(credential_hint()) from exc
            raise

    # ---- trace logging -----------------------------------------------------

    def _save_trace(self, result: AgentResult) -> None:
        if self.trace_path is None:
            return
        self.trace_path.parent.mkdir(parents=True, exist_ok=True)
        with self.trace_path.open("a", encoding="utf-8") as f:
            f.write(format_trace(result))


def format_trace(result: AgentResult) -> str:
    """Render one run as a Markdown section for logs/agent_traces.md."""
    lines = [f"\n## {datetime.now():%Y-%m-%d %H:%M:%S} — \"{result.request.strip()[:80]}\"\n"]
    for s in result.steps:
        if s["kind"] == "input_guardrail":
            lines.append(f"- **Input guardrail:** `{s['category']}`")
        elif s["kind"] == "offline":
            lines.append("- **Offline mode** (no API key): care guide + scheduler only, Claude not called")
        elif s["kind"] == "model":
            lines.append(f"- **Step {s['step']} (Claude, stop: `{s['stop_reason']}`)**")
            for t in s["thinking"]:
                lines.append(f"  - Reasoning: {' '.join(t.split())}")
            if s["text"] and s["tool_calls"]:
                lines.append(f"  - Said: {' '.join(s['text'].split())}")
            for c in s["tool_calls"]:
                lines.append(f"  - Tool call: `{c['name']}({json.dumps(c['input'])})`")
        elif s["kind"] == "tool":
            status = "ERROR" if s["is_error"] else "ok"
            output = " ".join(s["output"].split())
            if len(output) > 300:
                output = output[:300] + "…"
            lines.append(f"  - Result ({s['name']}, {status}): {output}")
        elif s["kind"] == "output_guardrail":
            lines.append(f"- **Output guardrail flags:** {s['flags'] or 'none'}")
    answer = "\n  ".join(result.answer.splitlines())
    lines.append(f"- **Final answer:**\n  {answer}\n")
    return "\n".join(lines) + "\n"


class ToolInputError(Exception):
    """A tool call the guardrails rejected; its message is sent back to Claude."""


class MissingCredentialsError(RuntimeError):
    """Raised when the agent needs Claude but no valid API key is configured."""


def credential_hint() -> str:
    """Explain a rejected credential, naming which Anthropic variables are set (never their values)."""
    import os

    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_token = bool(os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    if not has_key and has_token:
        return (
            "Anthropic rejected the credential. ANTHROPIC_AUTH_TOKEN is set but ANTHROPIC_API_KEY is not, "
            "so the SDK sent the auth token. Run `unset ANTHROPIC_AUTH_TOKEN` and "
            "`export ANTHROPIC_API_KEY=sk-ant-...` (a key from console.anthropic.com), then try again."
        )
    if has_key:
        return (
            "Anthropic rejected ANTHROPIC_API_KEY. Check that it was copied completely (it starts with "
            "sk-ant-), has no extra quotes or spaces, and hasn't been revoked at console.anthropic.com."
        )
    return (
        "Anthropic rejected the saved login credential. Set ANTHROPIC_API_KEY to a key from "
        "console.anthropic.com, then try again."
    )
