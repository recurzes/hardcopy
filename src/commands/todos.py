from __future__ import annotations

import argparse
import textwrap

from datetime import datetime

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import build_llm_context
from src.llm import LLMError, llm_complete
from src.llm_context import format_context_block
from src.printer import get_printer, print_centered

WEEKLY_GOAL_TASKS = 20


def print_task_item(p, content):
    available_width = MAX_WIDTH - 4

    wrapped_lines = textwrap.wrap(content, width=available_width)

    if wrapped_lines:
        p.text(f"[ ] {wrapped_lines[0]}\n")

        for line in wrapped_lines[1:]:
            p.text(f"    {line}\n")

    else:
        p.text("[ ] ???\n")

    p.text("\n")


def generate_morning_brief(task_count: int) -> str | None:
    try:
        context = build_llm_context()
        profile = format_context_block(
            context,
            sections=["stats", "today", "yesterday", "capacity", "weekly", "week_tasks_so_far"],
        )
        week_tasks = context.get("week_tasks_so_far", 0)
        tasks_to_boss = max(0, WEEKLY_GOAL_TASKS - week_tasks)

        system_prompt = """You write a short RPG-style morning quest briefing for someone with ADHD.

Write exactly 3-4 short lines (max 40 chars each line if possible).
Include: streak status, level/XP if relevant, weekly boss progress, and power hour tip.
Be motivating, concrete, and urgent. No markdown. No bullet symbols."""
        user_prompt = (
            f"{profile}\n\n"
            f"Today's quest count on the contract: {task_count}\n"
            f"Tasks remaining to weekly boss goal: {tasks_to_boss}\n"
        )
        return llm_complete(system_prompt, user_prompt).strip()
    except LLMError as e:
        print(f"Morning brief skipped (LLM): {e}")
        return None
    except Exception as e:
        print(f"Morning brief skipped: {e}")
        return None


def print_morning_brief(p, brief: str) -> None:
    p.set(align="center", bold=True, font="a")
    p.text("--- QUEST BRIEF ---\n")
    p.set(bold=False)
    for line in brief.splitlines()[:4]:
        line = line.strip()
        if not line:
            continue
        wrapped = textwrap.wrap(line, width=MAX_WIDTH) or [line]
        for part in wrapped:
            p.text(f"{part}\n")
    p.text("\n")


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Print today's Todoist tasks as a daily contract")
    parser.add_argument(
        "--no-brief",
        action="store_true",
        help="Skip the LLM morning quest brief",
    )
    args = parser.parse_args(argv)

    try:
        if not TODOIST_API_KEY:
            print("TODOIST_API_KEY not set in environment variables.")
            return

        api = TodoistAPI(TODOIST_API_KEY)
        p = get_printer()

        if not p:
            return

        all_tasks = api.get_tasks()
        task_to_print = []
        today = datetime.now().date()

        for page in all_tasks:
            for task in page:
                due = task.due
                if not due:
                    continue
                if due.date == today.isoformat():
                    task_to_print.append(task)

        if not task_to_print:
            print("No tasks for today! Enjoy your freedom")
            return

        p.text("\n")
        print_centered(p, "================================")
        print_centered(p, "    DAILY QUEST LOG    ")
        print_centered(p, datetime.now().strftime("%Y-%m-%d"))
        print_centered(p, "================================")
        p.text("\n")

        if not args.no_brief:
            brief = generate_morning_brief(len(task_to_print))
            if brief:
                print_morning_brief(p, brief)

        p.set(align="left", font="a")

        for task in task_to_print:
            print_task_item(p, task.content)

        p.text("\n")
        p.text("--------------------------------\n")
        p.set(align="center", bold=True)
        p.text("I commit to these tasks.\n")
        p.set(align="left", bold=False)
        p.text("\n\n\n")
        p.text(" X ___________________________\n")
        p.text("          (Signature)\n")
        p.text("\n\n")

        p.cut()
        p.close()
        print(f"Successfully printed {len(task_to_print)} tasks")

    except Exception as e:
        print(f"Error: {e}")
        print("Tip: Check if the printer is connected and permissions are set.")


if __name__ == "__main__":
    main()
