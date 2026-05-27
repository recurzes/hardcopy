from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from datetime import date, datetime

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import build_llm_context
from src.llm import LLMError, llm_complete
from src.llm_context import format_context_block
from src.printer import get_printer, print_centered


def normalize_due(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def fetch_all_tasks(api: TodoistAPI) -> list:
    tasks = []
    for page in api.get_tasks():
        tasks.extend(page)
    return tasks


def summarize_tasks(tasks: list, today: date) -> list[dict]:
    summarized = []
    for task in tasks:
        due = normalize_due(task.due.date if task.due else None)
        days_overdue = (today - due).days if due and due < today else 0
        summarized.append(
            {
                "task_id": task.id,
                "content": task.content,
                "priority": max(1, min(4, 5 - task.priority)),
                "due_date": due.isoformat() if due else None,
                "days_overdue": days_overdue,
                "is_overdue": days_overdue > 0,
            }
        )
    return summarized


def build_pick_system_prompt() -> str:
    return """You are a focus coach for someone with ADHD who is paralyzed by choice.

Pick exactly ONE task from the provided list. Rules:
- Prefer overdue tasks when energy allows
- If daily streak is at risk and no tasks completed today, pick the easiest 5-15 min win
- Prefer tasks matching their current hour productivity pattern when possible
- Avoid tasks they repeatedly capture but never complete if an easier win exists
- Return ONLY valid JSON (no markdown):
{
  "task_id": "id-from-list",
  "content": "task text",
  "reason": "one short sentence why this one"
}"""


def build_pick_user_prompt(task_list: list[dict], context_block: str) -> str:
    payload = {"tasks": task_list}
    return f"{context_block}\n\nCurrent hour: {datetime.now().hour:02d}:00\n\n{json.dumps(payload, indent=2)}"


def parse_pick_json(raw: str) -> dict:
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        text = fence_match.group(1).strip()

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")

    data = json.loads(text[start:])
    task_id = str(data.get("task_id", "")).strip()
    content = str(data.get("content", "")).strip()
    if not task_id or not content:
        raise ValueError("LLM response missing task_id or content")
    return {
        "task_id": task_id,
        "content": content,
        "reason": str(data.get("reason", "")).strip(),
    }


def print_pick_receipt(pick: dict) -> None:
    p = get_printer()
    if not p:
        return

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "     YOUR ONLY QUEST")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    wrapped = textwrap.wrap(pick["content"], width=MAX_WIDTH - 4) or [pick["content"]]
    for line in wrapped:
        p.text(f"{line}\n")
    if pick.get("reason"):
        p.text("\nWHY THIS ONE:\n")
        reason_wrapped = textwrap.wrap(pick["reason"], width=MAX_WIDTH - 4) or [pick["reason"]]
        for line in reason_wrapped:
            p.text(f"{line}\n")
    p.text("\n")
    print_centered(p, "Run focus on this now.")
    print_centered(p, "================================")
    p.text("\n\n")
    p.cut()
    p.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM picks one Todoist task to focus on using your behavior data"
    )
    parser.parse_args(argv)

    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return 1

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        tasks = fetch_all_tasks(api)
    except Exception as e:
        print(f"Todoist error: {e}")
        return 1

    if not tasks:
        print("No active tasks in Todoist.")
        return 0

    today = datetime.now().date()
    task_list = summarize_tasks(tasks, today)
    context = build_llm_context()
    context_block = format_context_block(
        context,
        sections=["stats", "today", "capacity", "plan_adherence"],
    )

    print("Choosing your quest...\n")
    try:
        raw = llm_complete(
            build_pick_system_prompt(),
            build_pick_user_prompt(task_list, context_block),
        )
        pick = parse_pick_json(raw)
    except LLMError as e:
        print(f"LLM error: {e}")
        return 1
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Failed to parse LLM response: {e}")
        return 1

    valid_ids = {task["task_id"] for task in task_list}
    if pick["task_id"] not in valid_ids:
        print(f"Warning: LLM returned unknown task_id {pick['task_id']!r}")

    print(f'Picked: "{pick["content"]}"')
    if pick.get("reason"):
        print(f"Reason: {pick['reason']}")
    print("\nPrinting receipt...")
    print_pick_receipt(pick)
    print(f'\nStart focus: python3 -m src.commands.focus "{pick["content"]}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
