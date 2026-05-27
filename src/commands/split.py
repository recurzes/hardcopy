from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from dataclasses import dataclass
from datetime import date, datetime

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import build_llm_context
from src.llm import LLMError, llm_complete
from src.llm_context import format_focus_context_block
from src.printer import get_printer, print_centered

BROAD_VERBS = (
    "write",
    "build",
    "prepare",
    "organize",
    "clean",
    "create",
    "develop",
    "implement",
    "design",
    "plan",
    "set up",
    "research",
    "review",
    "update",
    "fix",
)


@dataclass
class SplitTarget:
    content: str
    due_date: date | None
    priority: int
    task_id: str | None = None
    project_id: str | None = None


def normalize_due(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def task_duration_minutes(task) -> int | None:
    if task.duration and task.duration.unit == "minute":
        return task.duration.amount
    return None


def todoist_priority_to_display(priority: int) -> int:
    return max(1, min(4, 5 - priority))


def has_broad_verb(content: str) -> bool:
    content_lower = content.lower()
    return any(verb in content_lower for verb in BROAD_VERBS)


def fetch_all_tasks(api: TodoistAPI) -> list:
    tasks = []
    for page in api.get_tasks():
        tasks.extend(page)
    return tasks


def parents_with_children(tasks: list) -> set[str]:
    return {task.parent_id for task in tasks if task.parent_id}


def is_splittable(task, child_parent_ids: set[str]) -> bool:
    if task.parent_id:
        return False
    if task.id in child_parent_ids:
        return False
    if not has_broad_verb(task.content):
        return False
    duration = task_duration_minutes(task)
    if duration is not None and duration <= 60:
        return False
    return True


def looks_splittable_content(content: str) -> bool:
    return has_broad_verb(content)


def task_to_split_target(task) -> SplitTarget:
    return SplitTarget(
        content=task.content,
        due_date=normalize_due(task.due.date if task.due else None),
        priority=todoist_priority_to_display(task.priority),
        task_id=task.id,
        project_id=task.project_id,
    )


def format_due_label(due_date: date | None) -> str:
    if due_date is None:
        return "no date"
    return due_date.strftime("%b %-d")


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"~{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"~{hours}h {mins}m"
    return f"~{hours}h"


def build_split_system_prompt() -> str:
    context = build_llm_context()
    focus_block = format_focus_context_block(context["focus"])
    target_minutes = context["focus"].get("average_session_minutes") or 20
    max_subtasks = 7
    remaining = context["focus"].get("remaining_daily_capacity")
    if remaining is not None and remaining <= 1:
        max_subtasks = 4

    return f"""You are a task decomposition assistant for someone with ADHD.

{focus_block}

Given a large task, break it into 3-{max_subtasks} concrete subtasks. Each subtask must be:
- Completable in one sitting (~{target_minutes} minutes when possible)
- Specific and actionable (not vague)
- Ordered logically (dependencies first)

If remaining daily capacity is low, prefer fewer subtasks starting today.
Spread subtask due dates across the days before the parent deadline so work is not back-loaded.
If there is no parent due date, spread subtasks across the next few days starting from today.

Respond with ONLY valid JSON (no markdown fences):
{{
  "subtasks": [
    {{"content": "Gather 3 key sources and skim abstracts", "due_date": "YYYY-MM-DD", "estimated_minutes": 20}}
  ]
}}"""


def build_split_user_prompt(target: SplitTarget, today: date) -> str:
    context = build_llm_context()
    focus_block = format_focus_context_block(context["focus"])
    due_str = target.due_date.isoformat() if target.due_date else "none"
    return (
        f"{focus_block}\n\n"
        f'Today: {today.isoformat()} ({today.strftime("%A")})\n'
        f'Task: "{target.content}"\n'
        f"Priority: P{target.priority}\n"
        f"Due: {due_str}"
    )


def parse_subtasks_json(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        raise ValueError("LLM returned empty response")

    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")

    data = json.loads(text[start:])
    subtasks = data.get("subtasks") if isinstance(data, dict) else data
    if not isinstance(subtasks, list) or not subtasks:
        raise ValueError("LLM returned no subtasks")

    normalized = []
    for i, subtask in enumerate(subtasks, start=1):
        if not isinstance(subtask, dict):
            raise ValueError(f"Subtask {i} is not an object")
        content = str(subtask.get("content", "")).strip()
        if not content:
            raise ValueError(f"Subtask {i} is missing content")

        due_raw = subtask.get("due_date")
        due_date = date.fromisoformat(str(due_raw)) if due_raw else None

        estimated = subtask.get("estimated_minutes")
        estimated_minutes = int(estimated) if estimated is not None else None

        normalized.append(
            {
                "content": content,
                "due_date": due_date.isoformat() if due_date else None,
                "estimated_minutes": estimated_minutes,
            }
        )

    return normalized


def generate_subtasks(target: SplitTarget) -> list[dict]:
    today = datetime.now().date()
    raw = llm_complete(build_split_system_prompt(), build_split_user_prompt(target, today))
    return parse_subtasks_json(raw)


def show_proposed_split(target: SplitTarget, subtasks: list[dict]) -> None:
    print(f'\n"{target.content}" → {len(subtasks)} subtasks:')
    for i, subtask in enumerate(subtasks, start=1):
        duration = subtask.get("estimated_minutes")
        duration_str = f" ({duration} min)" if duration else ""
        print(f"  {i}. {subtask['content']}{duration_str}")


def create_subtasks(api: TodoistAPI, target: SplitTarget, subtasks: list[dict]) -> None:
    for subtask in subtasks:
        kwargs: dict = {"content": subtask["content"]}
        if target.task_id:
            kwargs["parent_id"] = target.task_id
        if target.project_id:
            kwargs["project_id"] = target.project_id
        if subtask.get("due_date"):
            kwargs["due_date"] = date.fromisoformat(subtask["due_date"])
        duration = subtask.get("estimated_minutes")
        if duration:
            kwargs["duration"] = int(duration)
            kwargs["duration_unit"] = "minute"
        api.add_task(**kwargs)


def print_subtask_line(p, subtask: dict) -> None:
    duration = subtask.get("estimated_minutes")
    duration_str = f" {duration}m" if duration else ""
    line = f"[ ] {subtask['content']}{duration_str}"
    available_width = MAX_WIDTH - 4
    wrapped = textwrap.wrap(line, width=available_width) or [line]
    p.text(f"{wrapped[0]}\n")
    for part in wrapped[1:]:
        p.text(f"    {part}\n")


def print_breakdown_receipt(
    parent_content: str,
    subtasks: list[dict],
    *,
    suggestion_only: bool = False,
) -> None:
    p = get_printer()
    if not p:
        return

    total_minutes = sum(subtask.get("estimated_minutes") or 0 for subtask in subtasks)
    title = "QUEST TOO BIG TO SOLO" if suggestion_only else "QUEST BREAKDOWN"

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, f"     {title}")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)

    print_wrapped_quote(p, f'"{parent_content}"')
    p.text("\n")
    if not suggestion_only:
        p.text(f"  → {len(subtasks)} micro-quests created\n\n")
    else:
        p.text("\nSuggested breakdown:\n")

    for subtask in subtasks:
        print_subtask_line(p, subtask)

    p.text("\n--------------------------------\n")
    p.set(align="center", bold=True)
    if suggestion_only:
        p.text("Run: python -m src.commands.split\n")
        p.text("to auto-create subtasks.\n")
    else:
        p.text(f"Total: {format_duration(total_minutes)}\n")
        p.text(f"{len(subtasks)} chances for XP rewards\n")
    p.set(align="left", bold=False)
    p.text("\n\n")
    p.cut()
    p.close()


def print_wrapped_quote(p, text: str) -> None:
    available_width = MAX_WIDTH - 4
    wrapped = textwrap.wrap(text, width=available_width) or [text]
    for line in wrapped:
        p.text(f"{line}\n")


def split_target_from_webhook(event_data: dict) -> SplitTarget:
    content = str(event_data.get("content", "")).strip()
    due = event_data.get("due") or {}
    due_date = normalize_due(due.get("date")) if due.get("date") else None
    priority = todoist_priority_to_display(int(event_data.get("priority", 1)))
    return SplitTarget(
        content=content,
        due_date=due_date,
        priority=priority,
        task_id=str(event_data.get("id")) if event_data.get("id") else None,
        project_id=str(event_data.get("project_id")) if event_data.get("project_id") else None,
    )


def print_split_suggestion_from_webhook(event_data: dict) -> None:
    content = str(event_data.get("content", "")).strip()
    if not looks_splittable_content(content):
        return

    target = split_target_from_webhook(event_data)
    try:
        subtasks = generate_subtasks(target)
    except (LLMError, ValueError, json.JSONDecodeError) as e:
        print(f"Split suggestion skipped: {e}")
        return

    print_breakdown_receipt(target.content, subtasks, suggestion_only=True)


def process_candidate(
    api: TodoistAPI,
    task,
    *,
    assume_yes: bool = False,
) -> bool:
    target = task_to_split_target(task)

    if assume_yes:
        try:
            subtasks = generate_subtasks(target)
            create_subtasks(api, target, subtasks)
            print_breakdown_receipt(target.content, subtasks)
            return True
        except (LLMError, ValueError, json.JSONDecodeError) as e:
            print(f"   Error: {e}")
            return False

    while True:
        choice = input("   → Split into subtasks? [Y/n/s] ").strip().lower()
        if choice in ("n", "no"):
            return False
        if choice in ("s", "show"):
            try:
                subtasks = generate_subtasks(target)
            except (LLMError, ValueError, json.JSONDecodeError) as e:
                print(f"   Error: {e}")
                return False
            show_proposed_split(target, subtasks)
            apply = input("\nApply? [Y/n]: ").strip().lower()
            if apply in ("n", "no"):
                return False
            create_subtasks(api, target, subtasks)
            print_breakdown_receipt(target.content, subtasks)
            return True
        if choice in ("", "y", "yes"):
            try:
                subtasks = generate_subtasks(target)
                create_subtasks(api, target, subtasks)
                print_breakdown_receipt(target.content, subtasks)
                return True
            except (LLMError, ValueError, json.JSONDecodeError) as e:
                print(f"   Error: {e}")
                return False
        print("Please enter Y, n, or s.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Split large Todoist tasks into ADHD-friendly micro-tasks"
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Split all candidates without prompting",
    )
    args = parser.parse_args(argv)

    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return 1

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        tasks = fetch_all_tasks(api)
        child_ids = parents_with_children(tasks)
        candidates = [task for task in tasks if is_splittable(task, child_ids)]
    except Exception as e:
        print(f"Todoist error: {e}")
        return 1

    print("Scanning for splittable tasks...\n")
    if not candidates:
        print("No splittable tasks found.")
        return 0

    print(f"Found {len(candidates)} tasks that could be broken down:\n")
    split_count = 0

    for i, task in enumerate(candidates, start=1):
        due_label = format_due_label(normalize_due(task.due.date if task.due else None))
        print(f'{i}. "{task.content}" (due: {due_label}, no subtasks)')
        if process_candidate(api, task, assume_yes=args.yes):
            split_count += 1
        print()

    if split_count:
        print(f"Split {split_count} task(s) into micro-quests.")
    else:
        print("No tasks were split.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
