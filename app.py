import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler, format_minutes, time_to_minutes

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.caption(
    "Plan your pets' care day: add pets and tasks, build a schedule that fits your time, "
    "or ask the AI assistant to do it for you in plain language."
)

st.divider()

# Keep one Owner across reruns so pets and tasks are not lost on each click.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_minutes=60)
owner = st.session_state.owner
scheduler = Scheduler(owner)


def task_rows(tasks: list[Task]) -> list[dict]:
    """Turn tasks into table rows for display."""
    return [
        {
            "due": f"{t.due_date:%m/%d}",
            "time": t.time or "anytime",
            "task": t.description,
            "pet": t.pet_name,
            "minutes": t.duration_minutes,
            "priority": t.priority,
            "frequency": t.frequency,
            "status": "done" if t.completed else "to do",
        }
        for t in tasks
    ]


st.subheader("Owner")
owner.name = st.text_input("Owner name", value=owner.name)
owner.available_minutes = int(
    st.number_input(
        "Minutes available today", min_value=0, max_value=1440, value=owner.available_minutes
    )
)

st.subheader("Add a Pet")
col1, col2, col3 = st.columns(3)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])
with col3:
    age = st.number_input("Age", min_value=0, max_value=40, value=2)

if st.button("Add pet"):
    if not pet_name.strip():
        st.error("Please enter a pet name.")
    elif owner.get_pet(pet_name.strip()):
        st.error(f"{pet_name.strip()} is already added.")
    else:
        owner.add_pet(Pet(name=pet_name.strip(), species=species, age=int(age)))
        st.success(f"Added {pet_name.strip()}.")

if owner.pets:
    st.write("Your pets:")
    st.table([{"name": p.name, "species": p.species, "age": p.age} for p in owner.pets])
else:
    st.info("No pets yet. Add one above.")

st.subheader("Schedule a Task")
if not owner.pets:
    st.caption("Add a pet first, then you can add tasks for it.")
else:
    task_pet = st.selectbox("For which pet?", [p.name for p in owner.pets])
    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task description", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", ["low", "medium", "high"], index=2)
    col4, col5 = st.columns(2)
    with col4:
        task_time = st.text_input("Time (HH:MM, optional)", value="")
    with col5:
        frequency = st.selectbox("Frequency", ["daily", "weekly", "once"])

    if st.button("Add task"):
        time_text = task_time.strip()
        start = time_to_minutes(time_text)
        if not task_title.strip():
            st.error("Please enter a task description.")
        elif time_text and start is None:
            st.error("Time must look like 08:30 (24-hour clock), or be left blank.")
        else:
            new_task = Task(
                description=task_title.strip(),
                duration_minutes=int(duration),
                priority=priority,
                # Store times zero-padded ("7:30" -> "07:30") so they display evenly.
                time=format_minutes(start) if start is not None else "",
                frequency=frequency,
            )
            owner.get_pet(task_pet).add_task(new_task)
            st.success(f"Added '{new_task.description}' for {task_pet}.")

            # Warn right away if the new task clashes with something due today.
            clashes = [
                w
                for w in scheduler.detect_conflicts(scheduler.get_pending_tasks())
                if f"'{new_task.description}'" in w
            ]
            for warning in clashes:
                st.warning(warning)

if owner.get_all_tasks():
    st.subheader("Your Tasks")
    col1, col2 = st.columns(2)
    with col1:
        pet_filter = st.selectbox("Show pet", ["All pets"] + [p.name for p in owner.pets])
    with col2:
        status_filter = st.selectbox("Show status", ["To do", "Done", "All"])

    shown = scheduler.filter_tasks(
        pet_name=None if pet_filter == "All pets" else pet_filter,
        completed={"To do": False, "Done": True, "All": None}[status_filter],
    )
    shown = scheduler.sort_by_time(shown)

    if shown:
        st.caption("Sorted by time; tasks without a time are listed last.")
        st.table(task_rows(shown))
    else:
        st.info("No tasks match these filters.")

    pending = scheduler.sort_by_time(scheduler.filter_tasks(completed=False))
    if pending:
        col1, col2 = st.columns([3, 1])
        with col1:
            to_complete = st.selectbox(
                "Mark a task complete",
                range(len(pending)),
                format_func=lambda i: (
                    f"{pending[i].description} for {pending[i].pet_name} "
                    f"(due {pending[i].due_date:%m/%d}"
                    f"{', ' + pending[i].time if pending[i].time else ''})"
                ),
            )
        with col2:
            st.write("")  # aligns the button with the select box
            if st.button("Complete"):
                task = pending[to_complete]
                next_task = scheduler.mark_task_complete(task)
                message = f"Completed '{task.description}'."
                if next_task:
                    message += (
                        f" Next {task.frequency} occurrence added for "
                        f"{next_task.due_date:%A, %m/%d}."
                    )
                # Keep the message across the rerun that refreshes the tables.
                st.session_state.flash = message
                st.rerun()

    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))

st.divider()

st.subheader("Build Schedule")

if st.button("Generate schedule"):
    plan = scheduler.generate_plan()

    if not plan and not scheduler.skipped:
        st.info("No pending tasks to schedule. Add some tasks above.")
    else:
        st.markdown(f"### Today's Schedule for {owner.name}")
        if plan:
            st.table(
                [
                    {
                        "time": t.time or "anytime",
                        "task": t.description,
                        "pet": t.pet_name,
                        "minutes": t.duration_minutes,
                        "priority": t.priority,
                    }
                    for t in plan
                ]
            )
        st.caption(
            f"{scheduler.total_scheduled_minutes()} of {owner.available_minutes} minutes used."
        )
        if scheduler.conflicts:
            st.error(f"⚠️ {len(scheduler.conflicts)} time conflict(s) in this plan:")
            for warning in scheduler.conflicts:
                st.warning(warning.removeprefix("Warning: "))
        else:
            st.success("No time conflicts in this plan.")

        if scheduler.skipped:
            st.warning(
                "Skipped (not enough time): "
                + ", ".join(f"{t.description} for {t.pet_name}" for t in scheduler.skipped)
            )
        with st.expander("Why this plan?"):
            st.text(scheduler.explain_plan())

st.divider()

st.subheader("🤖 Ask PawPal+")
st.caption(
    "Ask a pet care question or describe tasks in plain language, e.g. "
    "\"Mochi needs her pill at 8:00 every day, then plan my day.\" "
    "The assistant can add tasks to your list above and answers care questions "
    "from the PawPal+ care guide, with sources."
)

request = st.text_area("Your request", key="ai_request", height=80)
if st.button("Ask"):
    st.session_state.pop("ai_result", None)  # don't show a stale answer if this one fails
    # Imported here so the rest of the app works even without the anthropic package.
    try:
        import anthropic

        from agent import MissingCredentialsError, PawPalAgent
    except ImportError:
        st.error("Install the AI dependencies first: pip install -r requirements.txt")
    else:
        if not owner.pets:
            st.info("Tip: add a pet first so the assistant has someone to plan for.")
        with st.spinner("Thinking..."):
            try:
                result = PawPalAgent(owner).run(request)
            except MissingCredentialsError as exc:
                st.warning(
                    f"{exc} Restart the app after changing it. "
                    "Meanwhile, here is an offline answer from the care guide and scheduler (no AI)."
                )
                result = PawPalAgent(owner).run_offline(request)
            except anthropic.APIConnectionError:
                st.error("Couldn't reach the Anthropic API. Check your internet connection.")
                result = None
            except anthropic.APIStatusError as exc:
                st.error(f"The AI service returned an error ({exc.status_code}). Please try again.")
                result = None
        if result is not None:
            st.session_state.ai_result = result
            if result.tasks_added:
                # Rerun so the task tables above show the new tasks.
                st.rerun()

if "ai_result" in st.session_state:
    result = st.session_state.ai_result
    if result.blocked == "emergency":
        st.error(result.answer)
    elif result.blocked:
        st.warning(result.answer)
    elif result.answer.startswith("[offline mode]"):
        st.text(result.answer)
    else:
        st.markdown(result.answer)
    if result.tasks_added:
        st.success("Added to your tasks: " + ", ".join(result.tasks_added))
    if result.flags:
        st.caption("Guardrail flags: " + ", ".join(result.flags))
    with st.expander("How the assistant got this answer"):
        for s in result.steps:
            if s["kind"] == "input_guardrail":
                st.write(f"Input check: `{s['category']}`")
            elif s["kind"] == "model":
                for t in s["thinking"]:
                    st.write(f"💭 {t}")
                for c in s["tool_calls"]:
                    st.write(f"🔧 `{c['name']}` {c['input']}")
            elif s["kind"] == "tool":
                status = "❌" if s["is_error"] else "✅"
                st.text(f"{status} {s['output'][:400]}")
            elif s["kind"] == "output_guardrail":
                st.write(f"Output check flags: {s['flags'] or 'none'}")
