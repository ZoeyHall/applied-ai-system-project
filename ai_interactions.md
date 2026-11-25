# AI Interactions Log

## Agentic workflow: PawPal+ assistant reasoning traces

The PawPal+ assistant ([agent.py](agent.py)) records every run as it happens, and each run is appended to a committed log file:

➡️ **[logs/agent_traces.md](logs/agent_traces.md)**: traces from the CLI and the Streamlit app
➡️ `logs/eval_traces.md`: traces from `python eval/run_eval.py --live` (created on the first live run)

Each trace shows the full decision chain for one request:

| Trace line | What it shows |
|---|---|
| `Input guardrail` | The `check_input()` verdict (`ok`, `emergency`, `injection`, ...) |
| `Offline mode` | Present when no API key was available; the care guide and scheduler answered without Claude |
| `Step N (Claude, stop: ...)` | One model turn and why it stopped (`tool_use` = wants a tool, `end_turn` = finished) |
| `Reasoning:` | Claude's summarized reasoning for that step (adaptive thinking) |
| `Tool call:` | The tool Claude chose and its exact arguments |
| `Result (tool, ok/ERROR):` | What the tool returned, including validation errors sent back to Claude |
| `Output guardrail flags` | `dose_mentioned`, `uncited_advice`, or none |
| `Final answer` | What the owner saw |

### Example trace (from logs/agent_traces.md)

Recorded with `python assistant_cli.py --offline --demo`:

```markdown
## 2026-11-25 11:25:33 — "What does my day look like?"

- **Input guardrail:** `ok`
- **Offline mode** (no API key): care guide + scheduler only, Claude not called
  - Result (generate_plan, ok): Plan for Jordan: 85 of 90 minutes used. - 07:30: Breakfast for Mochi (10 min, high priority) - ...
- **Output guardrail flags:** none
- **Final answer:**
  [offline mode] Here is today's plan from the PawPal+ scheduler:
  Plan for Jordan: 85 of 90 minutes used.
  - 07:30: Breakfast for Mochi (10 min, high priority)
  - 07:30: Morning walk for Biscuit (30 min, high priority)
  - 08:00: Breakfast for Biscuit (10 min, high priority)
  - 20:00: Laser pointer play for Mochi (25 min, low priority)
  - any time: Clean litter box for Mochi (10 min, medium priority)
  Warning: 'Breakfast' (07:30-07:40) overlaps 'Morning walk' (07:30-08:00) for Mochi and Biscuit.
```

With an API key, the same request adds one `Step N (Claude ...)` block per model turn, each with `Reasoning:`, `Tool call:` and `Result` lines (for example `list_pets` → `add_task` → `generate_plan`). The unit test `test_trace_records_reasoning_and_tool_calls` checks that format.

---

## Using an AI agent during development

**What task did I give the agent?**

I used Claude Code in VS Code. I gave it the Project 4 rubric and asked it to improve my Module 2 PawPal+ project to meet it.

**What did the agent do?**

1. Read the rubric and my existing code (`pawpal_system.py`, `app.py`, `main.py`, tests, docs) and proposed a design: a tool-use agent on top of my existing scheduler, care-guide retrieval, guardrails, and an evaluation script.
2. Wrote the new modules (`agent.py`, `retriever.py`, `guardrails.py`, `assistant_cli.py`), the five care-guide documents in `knowledge/`, 23 new tests, `eval/run_eval.py` and `eval/compare_retrieval.py`.
3. Ran `pytest` and the evaluation after each change, and smoke-tested the Streamlit app headlessly with Streamlit's `AppTest`.
4. Rewrote the README, added the architecture diagram, and drafted these docs.

**What did I have to verify or fix?**

- **A test bug.** One new agent test failed on its first run. The fake client stored a reference to the message list, which kept growing afterwards, so the test was reading the wrong message. The agent code was fine. We fixed the test.
- **A UI bug found by testing.** The headless Streamlit test showed that after a failed request, the *previous* answer was still on screen. We fixed the app to clear the old answer when you click Ask.
- **My API key error.** When I first ran the demo I got a raw `401 Invalid bearer token` traceback. The agent worked out that my terminal was sending an `ANTHROPIC_AUTH_TOKEN` instead of an API key. It changed the app and CLI to explain this kind of error in plain words instead of crashing.
- **No API key.** I didn't have a working key, so rather than leave placeholder output in the README, I asked for the project to work without one. That became offline mode, and all README sample output is real.
