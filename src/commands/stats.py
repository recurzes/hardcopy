from __future__ import annotations

import argparse
import sys
from datetime import datetime

from src.db import (
    format_record_label,
    get_hourly_pattern,
    get_records,
    get_stats,
    get_today_summary,
    get_weekly_history,
)
from src.printer import get_printer, print_centered


def format_peak_hour(hourly_pattern: dict[int, int]) -> str:
    if not hourly_pattern:
        return "Not enough data yet"
    peak_hour = max(hourly_pattern, key=hourly_pattern.get)
    return f"{peak_hour:02d}:00 ({hourly_pattern[peak_hour]} tasks)"


def print_character_sheet() -> None:
    p = get_printer()
    if not p:
        return

    stats = get_stats()
    today = get_today_summary()
    records = get_records()
    history = get_weekly_history(weeks=1)
    hourly_pattern = get_hourly_pattern()

    level = int(stats.get("level", 1))
    total_xp = int(stats.get("total_xp", 0))
    xp_to_next = int(stats.get("xp_to_next", 0))
    daily_streak = int(stats.get("current_daily_streak", 0))
    focus_streak = int(stats.get("current_focus_streak", 0))
    total_tasks = int(stats.get("total_tasks_completed", 0))
    total_focus = int(stats.get("total_focus_sessions", 0))
    total_focus_minutes = int(stats.get("total_focus_minutes", 0))

    week_tasks = history[-1]["tasks_completed"] if history else 0

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "      CHARACTER SHEET")
    print_centered(p, datetime.now().strftime("%Y-%m-%d"))
    print_centered(p, "================================")
    p.text("\n")

    p.set(align="left", font="a", bold=True)
    p.text(f"LEVEL: {level}\n")
    p.set(bold=False)
    p.text(f"TOTAL XP: {total_xp}\n")
    p.text(f"NEXT LEVEL: {xp_to_next} XP\n\n")

    p.text("STREAKS:\n")
    p.text(f"- Daily: {daily_streak} days\n")
    p.text(f"- Focus: {focus_streak} sessions\n\n")

    p.text("TODAY:\n")
    p.text(f"- Tasks: {today['tasks_completed']}\n")
    p.text(f"- Focus: {today['focus_sessions']} ({today['focus_minutes']} min)\n")
    p.text(f"- XP: {today['xp_earned']}\n\n")

    p.text("LIFETIME:\n")
    p.text(f"- Tasks completed: {total_tasks}\n")
    p.text(f"- Focus sessions: {total_focus}\n")
    p.text(f"- Focus hours: {total_focus_minutes // 60}\n")
    p.text(f"- This week: {week_tasks} tasks\n\n")

    p.text("MOST PRODUCTIVE:\n")
    p.text(f"- Peak hour: {format_peak_hour(hourly_pattern)}\n\n")

    if records:
        p.text("PERSONAL RECORDS:\n")
        for record_type, record in records.items():
            label = format_record_label(record_type)
            p.text(f"- {label}: {record['value']}\n")
        p.text("\n")

    print_centered(p, "================================")
    p.text("\n\n")
    p.cut()
    p.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print a character sheet receipt with progress stats"
    )
    parser.parse_args(argv)

    print("Printing character sheet...")
    print_character_sheet()
    return 0


if __name__ == "__main__":
    sys.exit(main())
