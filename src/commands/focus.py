from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from todoist_api_python.api import TodoistAPI

from src.commands.reward import (
    ASCII_FRAMES,
    QUOTES,
    beep,
    get_reward_tier,
    get_time_bonus,
    print_ascii_art,
)
from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.printer import get_printer, print_centered

FOCUS_XP_MULTIPLIER = 1.5
TIER_BASE_XP = {
    "common": 75,
    "rare": 150,
    "epic": 300,
    "legendary": 500,
}
STREAK_PATH = Path.home() / ".local/share/hardcopy/focus_streaks.json"
DEFAULT_STREAK = {
    "current_streak": 0,
    "last_session_date": None,
    "total_sessions": 0,
    "total_minutes": 0,
}


@dataclass
class FocusSession:
    task: str
    duration_minutes: int
    start_monotonic: float = field(default_factory=time.monotonic)
    start_clock: datetime = field(default_factory=datetime.now)
    checkin_enabled: bool = True
    checkin_done: bool = False
    ended: bool = False


_session: FocusSession | None = None


def parse_duration(raw: str) -> int:
    value = raw.strip().lower().rstrip("m")
    minutes = int(value)
    if minutes < 1:
        raise ValueError("Duration must be at least 1 minute")
    return minutes


def load_streak_state() -> dict:
    if not STREAK_PATH.exists():
        return dict(DEFAULT_STREAK)
    try:
        with STREAK_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        state = dict(DEFAULT_STREAK)
        state.update(data)
        return state
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: could not read streak file: {e}")
        return dict(DEFAULT_STREAK)


def save_streak_state(state: dict) -> None:
    STREAK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STREAK_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def update_streak_on_complete(state: dict, minutes: int) -> tuple[dict, bool]:
    today = datetime.now().date()
    today_str = today.isoformat()
    yesterday_str = (today - timedelta(days=1)).isoformat()
    last_date = state.get("last_session_date")
    streak_increased = False

    if last_date == today_str:
        pass
    elif last_date == yesterday_str:
        state["current_streak"] = int(state.get("current_streak", 0)) + 1
        streak_increased = True
    else:
        state["current_streak"] = 1
        streak_increased = last_date is None

    state["last_session_date"] = today_str
    state["total_sessions"] = int(state.get("total_sessions", 0)) + 1
    state["total_minutes"] = int(state.get("total_minutes", 0)) + minutes
    return state, streak_increased


def calc_focus_xp(tier: str, *, partial_ratio: float = 1.0) -> int:
    base = TIER_BASE_XP.get(tier, 75)
    return max(1, int(base * FOCUS_XP_MULTIPLIER * partial_ratio))


def progress_bar(ratio: float, width: int = 30) -> str:
    filled = int(width * min(max(ratio, 0.0), 1.0))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def wrap_text(p, text: str, *, indent: str = "", bold: bool = False) -> None:
    available_width = MAX_WIDTH - len(indent)
    wrapped = textwrap.wrap(text, width=available_width) or [text]
    p.set(bold=bold, align="left", font="a")
    p.text(f"{indent}{wrapped[0]}\n")
    for line in wrapped[1:]:
        p.text(f"{indent}    {line}\n")


def print_session_start_receipt(session: FocusSession, streak: int) -> None:
    p = get_printer()
    if not p:
        return

    end_time = session.start_clock + timedelta(minutes=session.duration_minutes)
    start_label = session.start_clock.strftime("%H:%M")
    end_label = end_time.strftime("%H:%M")

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "   FOCUS SESSION ACTIVE")
    print_centered(p, f"   {start_label} -> {end_label} ({session.duration_minutes} min)")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("YOUR ONLY QUEST:\n")
    wrap_text(p, f'"{session.task}"')
    p.text("\nRULES OF ENGAGEMENT:\n")
    p.text("- Phone on silent\n")
    p.text("- One tab only\n")
    p.text("- If stuck, write what's\n")
    p.text("  blocking you on paper\n\n")
    p.text(f"STREAK: {streak} sessions\n")
    print_centered(p, "================================")
    p.text("\n\n")
    p.cut()
    p.close()


def print_checkpoint_receipt(session: FocusSession, elapsed_minutes: int) -> None:
    p = get_printer()
    if not p:
        return

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "   CHECKPOINT")
    print_centered(
        p,
        f"   {elapsed_minutes} of {session.duration_minutes} minutes elapsed",
    )
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("Still working on:\n")
    wrap_text(p, f'"{session.task}"')
    p.text("\nAre you on track?\n")
    p.text("[ ] Yes, still focused\n")
    p.text("[ ] Drifted — refocusing now\n")
    p.text("\n\n")
    p.cut()
    p.close()


def print_session_complete_receipt(
    session: FocusSession,
    *,
    xp: int,
    streak: int,
    streak_increased: bool,
    total_sessions: int,
    total_minutes: int,
) -> None:
    p = get_printer()
    if not p:
        return

    end_time = datetime.now()
    start_label = session.start_clock.strftime("%H:%M")
    end_label = end_time.strftime("%H:%M")
    time_bonus = get_time_bonus()
    flavor = random.choice(QUOTES)
    ascii_frame = random.choice(ASCII_FRAMES)

    beep(p)
    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "   SESSION COMPLETE!")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("QUEST:\n")
    wrap_text(p, f'"{session.task}"')
    p.text(f"\nTIME:  {session.duration_minutes} minutes\n")
    p.text(f"      ({start_label} — {end_label})\n\n")

    print_ascii_art(p, ascii_frame)

    p.set(bold=True, align="center", font="a")
    p.text(f"+{xp} XP  (FOCUS BONUS)\n")
    p.set(bold=False, align="center", font="b")
    p.text(f"{time_bonus}\n\n")

    streak_line = f"STREAK: {streak} sessions"
    if streak_increased:
        streak_line += " (new!)"
    p.text(f"{streak_line}\n")
    hours = total_minutes // 60
    p.text(f"TOTAL:  {total_sessions} sessions / {hours} hrs\n\n")
    p.text(f'> "{flavor}" <\n')
    p.text("\n\n")
    p.cut()
    p.close()


def print_partial_receipt(session: FocusSession, elapsed_minutes: int, xp: int) -> None:
    p = get_printer()
    if not p:
        return

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "   SESSION ENDED EARLY")
    print_centered(
        p,
        f"   {elapsed_minutes} of {session.duration_minutes} minutes",
    )
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("QUEST:\n")
    wrap_text(p, f'"{session.task}"')
    p.text(f"\n+{xp} XP (partial credit)\n\n")
    p.text("Not every session is perfect.\n")
    p.text("You still showed up.\n")
    p.text("\n\n")
    p.cut()
    p.close()


def print_abandoned_receipt(session: FocusSession) -> None:
    p = get_printer()
    if not p:
        return

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, "   SESSION ABANDONED")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    wrap_text(p, f'"{session.task}"')
    p.text("\n\nNo XP — session too short.\n")
    p.text("Try again when ready.\n")
    p.text("\n\n")
    p.cut()
    p.close()


def find_matching_task(api: TodoistAPI, description: str):
    desc_lower = description.lower().strip()
    for page in api.get_tasks():
        for task in page:
            content_lower = task.content.lower()
            if content_lower == desc_lower or desc_lower in content_lower:
                return task
    return None


def complete_todoist_task(description: str) -> bool:
    if not TODOIST_API_KEY:
        print("TODOIST_API_KEY not set; skipping task completion.")
        return False

    try:
        api = TodoistAPI(TODOIST_API_KEY)
        match = find_matching_task(api, description)
        if not match:
            print("No matching Todoist task found to complete.")
            return False
        api.complete_task(match.id)
        print(f'Completed Todoist task: "{match.content}"')
        return True
    except Exception as e:
        print(f"Todoist error: {e}")
        return False


def elapsed_minutes(session: FocusSession) -> int:
    elapsed_seconds = time.monotonic() - session.start_monotonic
    return max(0, int(elapsed_seconds // 60))


def handle_interrupt(signum, frame) -> None:
    del signum, frame
    session = _session
    if session is None or session.ended:
        sys.exit(0)

    session.ended = True
    elapsed = elapsed_minutes(session)

    if elapsed >= 1:
        tier = get_reward_tier()
        ratio = min(1.0, elapsed / session.duration_minutes)
        xp = calc_focus_xp(tier, partial_ratio=ratio * 0.5)
        print(f"\n\nSession ended early after {elapsed} minute(s).")
        print_partial_receipt(session, elapsed, xp)
    else:
        print("\n\nSession abandoned.")
        print_abandoned_receipt(session)

    sys.exit(0)


def run_timer(session: FocusSession) -> None:
    total_seconds = session.duration_minutes * 60
    checkin_at = (
        total_seconds // 2
        if session.checkin_enabled and session.duration_minutes > 30
        else None
    )

    while True:
        elapsed_seconds = time.monotonic() - session.start_monotonic
        remaining = total_seconds - elapsed_seconds

        if remaining <= 0:
            break

        if checkin_at and not session.checkin_done and elapsed_seconds >= checkin_at:
            elapsed_min = int(elapsed_seconds // 60)
            print("\n\nCheckpoint — printing check-in receipt...")
            print_checkpoint_receipt(session, elapsed_min)
            session.checkin_done = True

        mins, secs = divmod(int(remaining), 60)
        ratio = elapsed_seconds / total_seconds
        bar = progress_bar(ratio)
        sys.stdout.write(f"\rTimer: {mins:02d}:{secs:02d} remaining {bar}")
        sys.stdout.flush()
        time.sleep(1)

    sys.stdout.write("\n")


def main(argv: list[str] | None = None) -> int:
    global _session

    parser = argparse.ArgumentParser(
        description="Run a timed focus session with printer accountability"
    )
    parser.add_argument("task", help="What to focus on")
    parser.add_argument(
        "duration",
        nargs="?",
        default="25",
        help="Session length in minutes (default: 25, suffix m optional)",
    )
    parser.add_argument(
        "--no-checkin",
        action="store_true",
        help="Disable mid-session check-in receipt for long sessions",
    )
    parser.add_argument(
        "--complete",
        action="store_true",
        help="Complete a matching Todoist task when the session finishes",
    )
    args = parser.parse_args(argv)

    try:
        duration_minutes = parse_duration(args.duration)
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    streak_state = load_streak_state()
    session = FocusSession(
        task=args.task.strip(),
        duration_minutes=duration_minutes,
        checkin_enabled=not args.no_checkin,
    )
    _session = session

    signal.signal(signal.SIGINT, handle_interrupt)

    print("Printing session card...\n")
    print_session_start_receipt(session, int(streak_state.get("current_streak", 0)))

    try:
        run_timer(session)
    except KeyboardInterrupt:
        return 0

    session.ended = True
    print("\nSession complete!")
    print("Printing reward...")

    tier = get_reward_tier()
    xp = calc_focus_xp(tier)
    streak_state, streak_increased = update_streak_on_complete(
        streak_state, session.duration_minutes
    )
    save_streak_state(streak_state)

    print_session_complete_receipt(
        session,
        xp=xp,
        streak=int(streak_state["current_streak"]),
        streak_increased=streak_increased,
        total_sessions=int(streak_state["total_sessions"]),
        total_minutes=int(streak_state["total_minutes"]),
    )

    if args.complete:
        complete_todoist_task(session.task)

    return 0


if __name__ == "__main__":
    sys.exit(main())
