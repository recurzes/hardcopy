from __future__ import annotations

import json
from datetime import date
from typing import Any

WEEKDAY_NAMES = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def format_context_block(context: dict[str, Any], *, sections: list[str] | None = None) -> str:
    """Serialize DB context into a prompt-friendly text block."""
    allowed = sections or [
        "stats",
        "today",
        "yesterday",
        "capacity",
        "focus",
        "records",
        "weekly",
        "week_tasks_so_far",
        "plan_adherence",
    ]
    lines: list[str] = ["USER BEHAVIOR PROFILE:"]

    if "stats" in allowed:
        stats = context.get("stats", {})
        lines.extend(
            [
                f"- Level {stats.get('level', 1)}, {stats.get('total_xp', 0)} XP "
                f"({stats.get('xp_to_next', 0)} to next level)",
                f"- Daily streak: {stats.get('current_daily_streak', 0)} days",
                f"- Focus streak: {stats.get('current_focus_streak', 0)} sessions",
                f"- Lifetime tasks completed: {stats.get('total_tasks_completed', 0)}",
            ]
        )

    if "today" in allowed:
        today = context.get("today", {})
        lines.append(
            f"- Today so far: {today.get('tasks_completed', 0)} tasks, "
            f"{today.get('focus_sessions', 0)} focus sessions "
            f"({today.get('focus_minutes', 0)} min), {today.get('xp_earned', 0)} XP"
        )

    if "yesterday" in allowed:
        yesterday = context.get("yesterday", {})
        lines.append(
            f"- Yesterday: {yesterday.get('tasks_completed', 0)} tasks, "
            f"{yesterday.get('focus_sessions', 0)} focus sessions"
        )

    if "capacity" in allowed:
        capacity = context.get("capacity", {})
        weekday_avg = capacity.get("weekday_average")
        overall_avg = capacity.get("overall_average")
        peak_hour = capacity.get("peak_hour")
        if weekday_avg is not None:
            weekday = WEEKDAY_NAMES[date.today().weekday()]
            lines.append(f"- Average tasks on {weekday}s: {weekday_avg:.1f}")
        if overall_avg is not None:
            lines.append(f"- Overall daily average: {overall_avg:.1f} tasks")
        if peak_hour is not None:
            lines.append(f"- Most productive hour: {peak_hour:02d}:00")

    if "focus" in allowed:
        focus = context.get("focus", {})
        if focus.get("average_session_minutes") is not None:
            lines.append(
                f"- Average focus session: {focus['average_session_minutes']} min"
            )
        if focus.get("longest_session_minutes") is not None:
            lines.append(
                f"- Longest focus session record: {focus['longest_session_minutes']} min"
            )
        if focus.get("remaining_daily_capacity") is not None:
            lines.append(
                f"- Estimated remaining capacity today: "
                f"{focus['remaining_daily_capacity']} tasks"
            )

    if "week_tasks_so_far" in allowed:
        lines.append(f"- Tasks completed this week: {context.get('week_tasks_so_far', 0)}")

    if "weekly" in allowed and context.get("weekly"):
        weekly = context["weekly"]
        if weekly:
            current = weekly[-1]
            lines.append(
                f"- Current week tasks: {current.get('tasks_completed', 0)} "
                f"(rank {current.get('rank') or 'pending'})"
            )

    if "records" in allowed and context.get("records"):
        record_bits = [
            f"{key}={value['value']}" for key, value in context["records"].items()
        ]
        if record_bits:
            lines.append(f"- Personal records: {', '.join(record_bits)}")

    if "plan_adherence" in allowed:
        adherence = context.get("plan_adherence", {})
        yesterday_plan = adherence.get("yesterday_plan")
        if yesterday_plan:
            planned = yesterday_plan.get("task_count", 0)
            completed = adherence.get("today_completed", 0)
            lines.append(
                f"- Yesterday's plan: {planned} tasks; completed today so far: {completed}"
            )
        avg_planned = adherence.get("tomorrow_weekday_avg_planned")
        avg_completed = adherence.get("tomorrow_weekday_avg_completed")
        tomorrow_weekday = adherence.get("tomorrow_weekday")
        if avg_planned is not None and tomorrow_weekday:
            completed_text = (
                f"{avg_completed:.1f}" if avg_completed is not None else "unknown"
            )
            lines.append(
                f"- On {tomorrow_weekday}s they average {avg_planned:.1f} planned "
                f"and {completed_text} completed next day"
            )
        history = adherence.get("history", [])[:3]
        for item in history:
            lines.append(
                f"- Plan history: {item['plan_date']} planned {item['planned']}, "
                f"next day completed {item['completed_next_day']}"
            )

    return "\n".join(lines)


def format_focus_context_block(focus: dict[str, Any]) -> str:
    lines = ["FOCUS PROFILE:"]
    if focus.get("average_session_minutes") is not None:
        lines.append(
            f"- Target subtask length: ~{focus['average_session_minutes']} minutes"
        )
    elif focus.get("longest_session_minutes") is not None:
        lines.append(
            f"- Longest successful focus: {focus['longest_session_minutes']} minutes"
        )
    else:
        lines.append("- Target subtask length: 15-25 minutes (default)")

    if focus.get("remaining_daily_capacity") is not None:
        lines.append(
            f"- Remaining task capacity today: {focus['remaining_daily_capacity']}"
        )
    if focus.get("tasks_completed_today") is not None:
        lines.append(f"- Tasks already completed today: {focus['tasks_completed_today']}")
    return "\n".join(lines)


def format_weekly_summary_block(summary: dict[str, Any]) -> str:
    return json.dumps(summary, indent=2)
