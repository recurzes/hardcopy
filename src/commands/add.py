from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

from todoist_api_python.api import TodoistAPI

from src.config import TODOIST_API_KEY

PRIORITY_PATTERN = re.compile(r"!([1-4])\b")

DATE_EXPRESSION = re.compile(
    r"\b("
    r"(?:by|on|due)\s+"
    r"(?:today|tomorrow|tonight|next\s+week|next\s+month|"
    r"next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"\d{4}-\d{2}-\d{2})"
    r"|today|tomorrow|tonight|next\s+week|next\s+month|"
    r"next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"in\s+\d+\s+days?|"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"\d{4}-\d{2}-\d{2}"
    r")\b",
    re.IGNORECASE,
)

USER_TO_TODOIST_PRIORITY = {1: 4, 2: 3, 3: 2, 4: 1}


@dataclass
class ParsedTask:
    content: str
    due_string: str | None
    priority: int | None


def parse_task_string(raw: str) -> ParsedTask:
    text = raw.strip()
    if not text:
        raise ValueError("Empty task")

    priority: int | None = None
    priority_match = PRIORITY_PATTERN.search(text)
    if priority_match:
        user_priority = int(priority_match.group(1))
        priority = USER_TO_TODOIST_PRIORITY[user_priority]
        text = PRIORITY_PATTERN.sub("", text).strip()

    due_string: str | None = None
    matches = list(DATE_EXPRESSION.finditer(text))
    if matches:
        match = matches[-1]
        due_string = match.group(0)
        due_string = re.sub(r"^(by|on|due)\s+", "", due_string, flags=re.IGNORECASE).strip()
        text = (text[: match.start()] + text[match.end() :]).strip()
        text = re.sub(r"\s+", " ", text).strip(" ,.-")

    content = text.strip()
    if not content:
        raise ValueError(f"Could not extract task content from: {raw!r}")

    return ParsedTask(content=content, due_string=due_string, priority=priority)


def format_confirmation(task) -> str:
    parts: list[str] = []
    if task.due and task.due.date:
        parts.append(f"due: {task.due.date}")
    if task.priority and task.priority > 1:
        parts.append(f"priority: {5 - task.priority}")

    if parts:
        return f'Added: "{task.content}" ({", ".join(parts)})'
    return f'Added: "{task.content}" (no date)'


def create_task(api: TodoistAPI, parsed: ParsedTask):
    kwargs: dict = {"content": parsed.content}
    if parsed.due_string:
        kwargs["due_string"] = parsed.due_string
        kwargs["due_lang"] = "en"
    if parsed.priority is not None:
        kwargs["priority"] = parsed.priority
    return api.add_task(**kwargs)


def read_input(text: str | None) -> str:
    if text:
        return text.strip()
    return input("Task: ").strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Quickly capture a task into Todoist"
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Task text (semicolon-separated for multiple). Omit for prompt.",
    )
    args = parser.parse_args(argv)

    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set in environment variables.")
        return 1

    raw = read_input(args.text)
    if not raw:
        print("No input provided.")
        return 1

    segments = [segment.strip() for segment in raw.split(";") if segment.strip()]
    if not segments:
        print("No input provided.")
        return 1

    parsed_tasks: list[ParsedTask] = []
    for segment in segments:
        try:
            parsed_tasks.append(parse_task_string(segment))
        except ValueError as e:
            print(f"Error: {e}")
            return 1

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        created = [create_task(api, parsed) for parsed in parsed_tasks]
    except Exception as e:
        print(f"Todoist error: {e}")
        return 1

    if len(created) == 1:
        print(format_confirmation(created[0]))
    else:
        print(f"Added {len(created)} tasks.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
