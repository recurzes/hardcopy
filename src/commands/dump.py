from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from datetime import date, datetime

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import build_llm_context, log_brain_dump
from src.llm import LLMError, llm_complete
from src.llm_context import format_context_block
from src.printer import get_printer, print_centered

PRIORITY_LABELS = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}


def build_system_prompt(today: date) -> str:
    context = build_llm_context()
    profile = format_context_block(
        context,
        sections=["stats", "today", "capacity", "focus"],
    )

    return f"""You are a task decomposition assistant for someone with ADHD.

Today is {today.isoformat()} ({today.strftime("%A")}).

{profile}

Break vague brain-dump input into 3-8 concrete Todoist tasks. Rules:
- Each task must be completable in one sitting (15-30 minutes max, or match their average focus length if known)
- Use specific, actionable wording (start with a verb)
- Spread tasks across days; do not overload a single day
- If they already completed many tasks today, cap new tasks per day at 1-2 and spread the rest
- Respect their weekday average; never schedule more per day than their typical capacity
- Infer due dates from context (e.g. "friday presentation" -> tasks before Friday)
- Priority: 1 = most urgent, 4 = lowest
- duration_minutes: integer estimate (15-30 typical, or their focus session average)

Respond with ONLY valid JSON (no markdown fences), in this shape:
{{
  "tasks": [
    {{
      "content": "Outline presentation key points",
      "due_date": "YYYY-MM-DD",
      "priority": 2,
      "duration_minutes": 15,
      "project_name": null
    }}
  ]
}}"""


def parse_tasks_json(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        raise ValueError("LLM returned empty response")

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    if start == -1:
        start = text.find("[")
    if start == -1:
        raise ValueError("No JSON object or array found in LLM response")

    text = text[start:]
    data = json.loads(text)

    if isinstance(data, list):
        tasks = data
    elif isinstance(data, dict):
        tasks = data.get("tasks") or data.get("items") or []
    else:
        raise ValueError("LLM JSON must be an object or array")

    if not isinstance(tasks, list) or not tasks:
        raise ValueError("LLM returned no tasks")

    normalized = []
    for i, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ValueError(f"Task {i} is not an object")
        content = str(task.get("content", "")).strip()
        if not content:
            raise ValueError(f"Task {i} is missing content")

        due_raw = task.get("due_date")
        if not due_raw:
            raise ValueError(f"Task {i} is missing due_date")
        due_date = date.fromisoformat(str(due_raw))

        priority = int(task.get("priority", 3))
        priority = max(1, min(4, priority))

        duration = task.get("duration_minutes", task.get("duration"))
        duration_minutes = int(duration) if duration is not None else None

        project_name = task.get("project_name")
        if project_name is not None:
            project_name = str(project_name).strip() or None

        normalized.append(
            {
                "content": content,
                "due_date": due_date.isoformat(),
                "priority": priority,
                "duration_minutes": duration_minutes,
                "project_name": project_name,
            }
        )

    return normalized


def llm_priority_to_todoist(priority: int) -> int:
    """Map display priority (1=urgent) to Todoist API priority (4=urgent)."""
    return max(1, min(4, 5 - priority))


def format_task_preview(task: dict) -> str:
    due = date.fromisoformat(task["due_date"])
    day = due.strftime("%a")
    label = PRIORITY_LABELS.get(task["priority"], "P?")
    duration = task.get("duration_minutes")
    duration_str = f" ({duration} min)" if duration else ""
    return f"  [{label}] {day}  - {task['content']}{duration_str}"


def read_brain_dump(args_text: str | None) -> str:
    if args_text:
        return args_text.strip()

    print("Enter brain dump (blank line when done):")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines:
            break
        if line.strip():
            lines.append(line.strip())

    return " ".join(lines)


def confirm_tasks(tasks: list[dict], assume_yes: bool) -> list[dict] | None:
    print(f"\nProposed {len(tasks)} tasks:\n")
    for task in tasks:
        print(format_task_preview(task))

    if assume_yes:
        return tasks

    while True:
        choice = input("\nCreate in Todoist? [Y/n/e] (e = edit): ").strip().lower()
        if choice in ("", "y", "yes"):
            return tasks
        if choice in ("n", "no"):
            print("Aborted. No tasks created.")
            return None
        if choice in ("e", "edit"):
            return edit_tasks(tasks)
        print("Please enter Y, n, or e.")


def edit_tasks(tasks: list[dict]) -> list[dict] | None:
    print("\nNumbered tasks:")
    for i, task in enumerate(tasks, start=1):
        print(f"{i}. {format_task_preview(task).strip()}")

    raw = input(
        "\nRemove tasks by number (comma-separated), or press Enter to keep all: "
    ).strip()
    if not raw:
        return confirm_tasks(tasks, assume_yes=False)

    to_remove: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part.isdigit():
            print(f"Ignoring invalid entry: {part!r}")
            continue
        to_remove.add(int(part))

    remaining = [task for i, task in enumerate(tasks, start=1) if i not in to_remove]
    if not remaining:
        print("No tasks left after edit. Aborted.")
        return None

    return confirm_tasks(remaining, assume_yes=False)


def fetch_project_map(api: TodoistAPI) -> dict[str, str]:
    projects: dict[str, str] = {}
    for page in api.get_projects():
        for project in page:
            projects[project.name.lower()] = project.id
    return projects


def create_tasks_in_todoist(api: TodoistAPI, tasks: list[dict]) -> list[dict]:
    project_map = fetch_project_map(api)
    created: list[dict] = []

    for task in tasks:
        kwargs: dict = {
            "content": task["content"],
            "due_date": date.fromisoformat(task["due_date"]),
            "priority": llm_priority_to_todoist(task["priority"]),
        }

        duration = task.get("duration_minutes")
        if duration:
            kwargs["duration"] = int(duration)
            kwargs["duration_unit"] = "minute"

        project_name = task.get("project_name")
        if project_name:
            project_id = project_map.get(project_name.lower())
            if project_id:
                kwargs["project_id"] = project_id
            else:
                print(f"Warning: project {project_name!r} not found; using inbox")

        api.add_task(**kwargs)
        created.append(task)

    return created


def print_task_line(p, task: dict) -> None:
    due = date.fromisoformat(task["due_date"])
    label = PRIORITY_LABELS.get(task["priority"], "P?")
    duration = task.get("duration_minutes")
    header = f"[{label}] {due.strftime('%a')} - {task['content']}"
    if duration:
        header += f" ({duration} min)"

    available_width = MAX_WIDTH - 4
    wrapped = textwrap.wrap(header, width=available_width) or [header]
    p.text(f"{wrapped[0]}\n")
    for line in wrapped[1:]:
        p.text(f"    {line}\n")


def print_briefing_receipt(tasks: list[dict]) -> None:
    p = get_printer()
    if not p:
        return

    today = datetime.now().strftime("%Y-%m-%d")
    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "      QUEST BRIEFING")
    print_centered(p, today)
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("New quests added to your log:\n\n")

    for task in tasks:
        print_task_line(p, task)
        p.text("\n")

    p.text("--------------------------------\n")
    p.set(align="center", bold=True)
    p.text(f"{len(tasks)} quests. You got this.\n")
    p.set(align="left", bold=False)
    p.text("\n\n")
    p.cut()
    p.close()


def confirm_print_receipt(assume_yes: bool) -> bool:
    if assume_yes:
        return True

    choice = input("\nPrint preview receipt? [Y/n]: ").strip().lower()
    return choice in ("", "y", "yes")


def decompose_brain_dump(text: str) -> list[dict]:
    today = datetime.now().date()
    system_prompt = build_system_prompt(today)
    print("Thinking...\n")
    raw = llm_complete(system_prompt, text)
    return parse_tasks_json(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Decompose a brain dump into organized Todoist tasks"
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Freeform brain dump text (omit for interactive input)",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompts",
    )
    parser.add_argument(
        "--no-print",
        action="store_true",
        help="Do not offer to print a briefing receipt",
    )
    args = parser.parse_args(argv)

    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return 1

    brain_dump = read_brain_dump(args.text)
    if not brain_dump:
        print("No input provided.")
        return 1

    try:
        tasks = decompose_brain_dump(brain_dump)
    except LLMError as e:
        print(f"LLM error: {e}")
        return 1
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Failed to parse LLM response: {e}")
        return 1

    confirmed = confirm_tasks(tasks, assume_yes=args.yes)
    if not confirmed:
        return 0

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        created = create_tasks_in_todoist(api, confirmed)
    except Exception as e:
        print(f"Todoist error: {e}")
        return 1

    print(f"\nCreated {len(created)} tasks in Todoist:")
    for task in created:
        print(format_task_preview(task))

    try:
        log_brain_dump(len(created))
    except Exception as e:
        print(f"Database error: {e}")

    if not args.no_print and confirm_print_receipt(assume_yes=args.yes):
        print_briefing_receipt(created)

    return 0


if __name__ == "__main__":
    sys.exit(main())
