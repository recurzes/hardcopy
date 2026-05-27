from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from datetime import date, datetime, timedelta

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import get_capacity_insights, log_plan_generated
from src.llm import LLMError, llm_complete
from src.printer import get_printer, print_centered

PRIORITY_LABELS = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}


def todoist_priority_to_display(priority: int) -> int:
    return max(1, min(4, 5 - priority))


def normalize_due(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def format_duration(minutes: int) -> str:
    if minutes < 60:
        return f"~{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"~{hours}h {mins}m"
    return f"~{hours}h"


def fetch_all_tasks(api: TodoistAPI) -> list:
    tasks = []
    for page in api.get_tasks():
        tasks.extend(page)
    return tasks


def fetch_recent_completion_count(api: TodoistAPI, days: int = 7) -> int:
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    completed = []
    for page in api.get_completed_tasks_by_completion_date(
        since=start_date, until=end_date
    ):
        completed.extend(page)
    return len(completed)


def task_duration_minutes(task) -> int | None:
    if task.duration and task.duration.unit == "minute":
        return task.duration.amount
    return None


def summarize_task(task, today: date) -> dict:
    due = normalize_due(task.due.date if task.due else None)
    days_overdue = (today - due).days if due and due < today else 0
    duration = task_duration_minutes(task)

    return {
        "task_id": task.id,
        "content": task.content,
        "priority": todoist_priority_to_display(task.priority),
        "due_date": due.isoformat() if due else None,
        "days_overdue": days_overdue,
        "duration_minutes": duration,
    }


def categorize_tasks(tasks: list, today: date, tomorrow: date) -> dict:
    overdue: list[dict] = []
    due_tomorrow: list[dict] = []
    upcoming: list[dict] = []
    unscheduled: list[dict] = []
    week_end = today + timedelta(days=7)

    for task in tasks:
        summary = summarize_task(task, today)
        due = normalize_due(task.due.date if task.due else None)

        if due is None:
            unscheduled.append(summary)
        elif due < today:
            overdue.append(summary)
        elif due == tomorrow:
            due_tomorrow.append(summary)
        elif today < due <= week_end:
            upcoming.append(summary)

    return {
        "overdue": overdue,
        "due_tomorrow": due_tomorrow,
        "upcoming": upcoming,
        "unscheduled": unscheduled,
    }


def gather_context(api: TodoistAPI) -> dict:
    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    tasks = fetch_all_tasks(api)
    buckets = categorize_tasks(tasks, today, tomorrow)

    completed_last_7_days = fetch_recent_completion_count(api)
    recent_daily_average = completed_last_7_days / 7

    capacity = get_capacity_insights(today)
    weekday_avg = capacity.get("weekday_average")
    overall_avg = capacity.get("overall_average")

    if weekday_avg is not None:
        suggested_task_count = int(min(max(round(weekday_avg), 3), 8))
        capacity_source = f"{today.strftime('%A')} average"
    elif overall_avg is not None:
        suggested_task_count = int(min(max(round(overall_avg), 3), 8))
        capacity_source = "your overall average"
    else:
        suggested_task_count = int(min(max(round(recent_daily_average), 3), 8))
        capacity_source = "Todoist last 7 days"

    return {
        "today": today,
        "tomorrow": tomorrow,
        "buckets": buckets,
        "completed_last_7_days": completed_last_7_days,
        "recent_daily_average": recent_daily_average,
        "suggested_task_count": suggested_task_count,
        "capacity_source": capacity_source,
        "capacity": capacity,
        "task_by_id": {task.id: task for task in tasks},
    }


def build_system_prompt(context: dict) -> str:
    today = context["today"]
    tomorrow = context["tomorrow"]
    suggested = context["suggested_task_count"]
    avg = context["recent_daily_average"]
    capacity = context.get("capacity", {})
    capacity_source = context.get("capacity_source", "recent pace")
    weekday_avg = capacity.get("weekday_average")
    overall_avg = capacity.get("overall_average")
    peak_hour = capacity.get("peak_hour")

    capacity_lines = [
        f"The user typically completes ~{avg:.1f} tasks/day (Todoist last 7 days).",
        f"Suggest about {suggested} tasks total for tomorrow based on {capacity_source} (never more than 8 unless overdue tasks alone exceed that).",
    ]
    if weekday_avg is not None:
        capacity_lines.append(
            f"They average {weekday_avg:.1f} tasks on {today.strftime('%A')}s."
        )
    if overall_avg is not None and weekday_avg is None:
        capacity_lines.append(f"Their overall average is {overall_avg:.1f} tasks/day.")
    if peak_hour is not None:
        capacity_lines.append(
            f"Their most productive hour is around {peak_hour:02d}:00."
        )

    capacity_text = "\n".join(capacity_lines)

    return f"""You are an evening planning assistant for someone with ADHD.

Today is {today.isoformat()} ({today.strftime("%A")}).
Tomorrow is {tomorrow.isoformat()} ({tomorrow.strftime("%A")}).

{capacity_text}

Rules:
- ALWAYS include every overdue task
- Select additional tasks from upcoming, unscheduled, and already-due-tomorrow lists
- Prefer variety across projects/types
- Each task must reference an existing task_id from the provided context
- Use priority 1 (most urgent) through 4 (lowest)
- estimated_minutes: integer guess (15-30 typical)
- reason: short note (e.g. "overdue by 2 days", "due tomorrow already")

Respond with ONLY valid JSON (no markdown fences):
{{
  "tasks": [
    {{
      "task_id": "existing-id",
      "content": "Task description",
      "priority": 2,
      "estimated_minutes": 15,
      "reason": "overdue by 2 days"
    }}
  ],
  "total_estimated_minutes": 120,
  "capacity_note": "Looks manageable based on your recent pace."
}}"""


def build_user_prompt(context: dict) -> str:
    payload = {
        "overdue": context["buckets"]["overdue"],
        "due_tomorrow": context["buckets"]["due_tomorrow"],
        "upcoming": context["buckets"]["upcoming"],
        "unscheduled": context["buckets"]["unscheduled"],
        "completed_last_7_days": context["completed_last_7_days"],
        "suggested_task_count": context["suggested_task_count"],
    }
    return json.dumps(payload, indent=2)


def parse_plan_json(raw: str) -> dict:
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
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object")

    tasks = data.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("LLM returned no tasks")

    normalized = []
    for i, task in enumerate(tasks, start=1):
        if not isinstance(task, dict):
            raise ValueError(f"Task {i} is not an object")

        task_id = str(task.get("task_id", "")).strip()
        content = str(task.get("content", "")).strip()
        if not task_id:
            raise ValueError(f"Task {i} is missing task_id")
        if not content:
            raise ValueError(f"Task {i} is missing content")

        priority = int(task.get("priority", 3))
        priority = max(1, min(4, priority))

        estimated = task.get("estimated_minutes")
        estimated_minutes = int(estimated) if estimated is not None else None

        normalized.append(
            {
                "task_id": task_id,
                "content": content,
                "priority": priority,
                "estimated_minutes": estimated_minutes,
                "reason": str(task.get("reason", "")).strip(),
            }
        )

    total = data.get("total_estimated_minutes")
    total_estimated_minutes = int(total) if total is not None else None
    capacity_note = str(data.get("capacity_note", "")).strip()

    return {
        "tasks": normalized,
        "total_estimated_minutes": total_estimated_minutes,
        "capacity_note": capacity_note,
    }


def plan_task_from_overdue(overdue: dict) -> dict:
    days = overdue.get("days_overdue", 0)
    reason = f"overdue by {days} day{'s' if days != 1 else ''}"
    return {
        "task_id": overdue["task_id"],
        "content": overdue["content"],
        "priority": overdue.get("priority", 1),
        "estimated_minutes": overdue.get("duration_minutes"),
        "reason": reason,
    }


def finalize_plan(plan: dict, context: dict) -> dict:
    valid_ids = set(context["task_by_id"])
    overdue_ids = {item["task_id"] for item in context["buckets"]["overdue"]}
    suggested = context["suggested_task_count"]

    selected_by_id: dict[str, dict] = {}
    for task in plan["tasks"]:
        if task["task_id"] not in valid_ids:
            print(f"Warning: ignoring unknown task_id {task['task_id']!r}")
            continue
        selected_by_id[task["task_id"]] = task

    result: list[dict] = []
    seen: set[str] = set()

    for overdue in context["buckets"]["overdue"]:
        task_id = overdue["task_id"]
        if task_id in selected_by_id:
            result.append(selected_by_id[task_id])
        else:
            result.append(plan_task_from_overdue(overdue))
        seen.add(task_id)

    others = [task for task_id, task in selected_by_id.items() if task_id not in seen]
    if len(result) > 8:
        target_total = len(result)
    else:
        target_total = min(max(suggested, len(result)), 8)
    remaining_slots = max(0, target_total - len(result))
    result.extend(others[:remaining_slots])

    if plan.get("total_estimated_minutes") is None:
        total_minutes = sum(
            task["estimated_minutes"] or 0 for task in result
        )
    else:
        total_minutes = plan["total_estimated_minutes"]

    capacity_note = plan.get("capacity_note") or "This plan is right-sized."

    return {
        "tasks": result,
        "total_estimated_minutes": total_minutes,
        "capacity_note": capacity_note,
        "overdue_ids": overdue_ids,
    }


def format_plan_preview(task: dict, overdue_ids: set[str]) -> str:
    label = PRIORITY_LABELS.get(task["priority"], "P?")
    duration = task.get("estimated_minutes")
    duration_str = f" ({duration} min)" if duration else ""

    if task["task_id"] in overdue_ids or "overdue" in task.get("reason", "").lower():
        days_match = re.search(r"(\d+)\s+day", task.get("reason", ""))
        if days_match:
            days = days_match.group(1)
            suffix = f" (overdue {days} day{'s' if days != '1' else ''})"
        else:
            suffix = " (overdue)"
        return f"  [{label}] {task['content']}{suffix}"

    return f"  [{label}] {task['content']}{duration_str}"


def print_plan_preview(plan: dict) -> None:
    overdue_ids = plan["overdue_ids"]
    print("\nTomorrow's draft plan:")
    for task in plan["tasks"]:
        print(format_plan_preview(task, overdue_ids))


def confirm_plan(plan: dict, auto: bool) -> str | None:
    if auto:
        return "apply"

    print_plan_preview(plan)

    while True:
        choice = input("\nApply to Todoist? [Y/n/e]\n  Y = reschedule all to tomorrow\n  n = print only, don't touch Todoist\n  e = edit list first\n> ").strip().lower()
        if choice in ("", "y", "yes"):
            return "apply"
        if choice in ("n", "no"):
            return "print_only"
        if choice in ("e", "edit"):
            edited = edit_plan(plan)
            if edited is None:
                return None
            plan.clear()
            plan.update(edited)
            print_plan_preview(plan)
            continue
        print("Please enter Y, n, or e.")


def edit_plan(plan: dict) -> dict | None:
    print("\nNumbered tasks:")
    for i, task in enumerate(plan["tasks"], start=1):
        print(f"{i}. {format_plan_preview(task, plan['overdue_ids']).strip()}")

    raw = input(
        "\nRemove tasks by number (comma-separated), or press Enter to keep all: "
    ).strip()
    if not raw:
        return plan

    to_remove: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part.isdigit():
            print(f"Ignoring invalid entry: {part!r}")
            continue
        to_remove.add(int(part))

    remaining = [
        task for i, task in enumerate(plan["tasks"], start=1) if i not in to_remove
    ]
    if not remaining:
        print("No tasks left after edit. Aborted.")
        return None

    updated = dict(plan)
    updated["tasks"] = remaining
    if updated.get("total_estimated_minutes") is not None:
        updated["total_estimated_minutes"] = sum(
            task["estimated_minutes"] or 0 for task in remaining
        )
    return updated


def apply_plan(api: TodoistAPI, plan: dict) -> None:
    for task in plan["tasks"]:
        api.update_task(task["task_id"], due_string="tomorrow", due_lang="en")


def print_wrapped_line(p, text: str, indent: str = "") -> None:
    available_width = MAX_WIDTH - len(indent)
    wrapped = textwrap.wrap(text, width=available_width) or [text]
    p.text(f"{indent}{wrapped[0]}\n")
    for line in wrapped[1:]:
        p.text(f"{indent}    {line}\n")


def print_battle_plan_receipt(plan: dict, context: dict) -> None:
    p = get_printer()
    if not p:
        return

    tomorrow = context["tomorrow"]
    overdue_ids = plan["overdue_ids"]
    overdue_tasks = [t for t in plan["tasks"] if t["task_id"] in overdue_ids]
    tomorrow_tasks = [t for t in plan["tasks"] if t["task_id"] not in overdue_ids]

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "  TOMORROW'S BATTLE PLAN")
    print_centered(p, tomorrow.strftime("%A, %B %-d"))
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)

    if overdue_tasks:
        p.text("CARRY-OVER (overdue):\n")
        for task in overdue_tasks:
            p.text("[!] ")
            print_wrapped_line(p, task["content"], indent="")
            days = next(
                (
                    item["days_overdue"]
                    for item in context["buckets"]["overdue"]
                    if item["task_id"] == task["task_id"]
                ),
                None,
            )
            if days:
                p.text(f"    ({days} day{'s' if days != 1 else ''} overdue)\n")
        p.text("\n")

    if tomorrow_tasks:
        p.text("TOMORROW'S QUESTS:\n")
        for task in tomorrow_tasks:
            duration = task.get("estimated_minutes")
            duration_str = f" {duration}m" if duration else ""
            line = f"[ ] {task['content']}{duration_str}"
            print_wrapped_line(p, line)
        p.text("\n")

    total_minutes = plan.get("total_estimated_minutes") or 0
    total_count = len(plan["tasks"])
    avg = round(context["recent_daily_average"])
    capacity = context.get("capacity", {})
    daily_streak = int(capacity.get("daily_streak", 0))
    last_active = capacity.get("last_active_date")
    today_str = context["today"].isoformat()
    streak_at_risk = daily_streak > 0 and last_active != today_str

    p.text("--------------------------------\n")
    p.set(align="center", bold=True)
    footer = f"Total: {format_duration(total_minutes)} | {total_count} quests\n"
    p.text(footer)
    p.text(f"You averaged {avg}/day last week.\n")
    if context.get("capacity_source"):
        p.text(f"Target based on {context['capacity_source']}.\n")
    if streak_at_risk:
        p.text(f"Complete 1 task to keep your {daily_streak}-day streak!\n")
    p.text(f"{plan.get('capacity_note', 'This plan is right-sized.')}\n")
    p.set(align="left", bold=False)
    p.text("\n\n")
    p.cut()
    p.close()


def generate_plan(context: dict) -> dict:
    system_prompt = build_system_prompt(context)
    user_prompt = build_user_prompt(context)
    print("Analyzing your Todoist...\n")
    raw = llm_complete(system_prompt, user_prompt)
    parsed = parse_plan_json(raw)
    return finalize_plan(parsed, context)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draft tomorrow's Todoist plan using LLM"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Non-interactive mode for systemd (apply + print)",
    )
    args = parser.parse_args(argv)

    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return 1

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        context = gather_context(api)
    except Exception as e:
        print(f"Todoist error: {e}")
        return 1

    if not context["task_by_id"]:
        print("No active tasks found in Todoist.")
        return 0

    try:
        plan = generate_plan(context)
    except LLMError as e:
        print(f"LLM error: {e}")
        return 1
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Failed to parse LLM response: {e}")
        return 1

    if not plan["tasks"]:
        print("No tasks selected for tomorrow.")
        return 0

    action = confirm_plan(plan, auto=args.auto)
    if action is None:
        return 0

    if action == "apply":
        try:
            apply_plan(api, plan)
            print(f"\nRescheduled {len(plan['tasks'])} tasks to tomorrow in Todoist.")
        except Exception as e:
            print(f"Todoist error: {e}")
            return 1

    print_battle_plan_receipt(plan, context)

    try:
        log_plan_generated(
            len(plan["tasks"]),
            plan.get("total_estimated_minutes"),
        )
    except Exception as e:
        print(f"Database error: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
