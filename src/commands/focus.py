from __future__ import annotations

import argparse
import random
import signal
import sys
import textwrap
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from todoist_api_python.api import TodoistAPI

from src.commands.reward import (
    ASCII_FRAMES,
    beep,
    get_reward_tier,
    get_time_bonus,
    print_ascii_art,
)
from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.db import (
    get_focus_streak_state,
    get_random_quote,
    log_focus_session,
    print_level_up_receipt,
    print_new_record_lines,
)
from src.printer import get_printer, print_centered

FOCUS_XP_MULTIPLIER = 1.5
TIER_BASE_XP = {
    "common": 75,
    "rare": 150,
    "epic": 300,
    "legendary": 500,
}


@dataclass
class FocusSession:
    task: str
    duration_minutes: int
    start_monotonic: float = field(default_factory=time.monotonic)
    start_clock: datetime = field(default_factory=datetime.now)
    checkin_enabled: bool = True
    update_1_done: bool = False
    update_2_done: bool = False
    ended: bool = False


_session: FocusSession | None = None


def parse_duration(raw: str) -> int:
    value = raw.strip().lower().rstrip("m")
    minutes = int(value)
    if minutes < 1:
        raise ValueError("Duration must be at least 1 minute")
    return minutes


def load_streak_state() -> dict:
    return get_focus_streak_state()


def calc_focus_xp(tier: str, *, partial_ratio: float = 1.0) -> int:
    base = TIER_BASE_XP.get(tier, 75)
    return max(1, int(base * FOCUS_XP_MULTIPLIER * partial_ratio))


def progress_bar(ratio: float, width: int = 28) -> str:
    ratio = min(max(ratio, 0.0), 1.0)
    if ratio == 0.0:
        return "[>" + " " * (width - 1) + "]"
    filled = int(width * ratio)
    if filled >= width:
        return "[" + "=" * width + "]"
    return "[" + "=" * filled + ">" + " " * (width - filled - 1) + "]"


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
    print_centered(p, "   FOCUS SESSION")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("TASK:\n")
    wrap_text(p, f'"{session.task}"')
    p.text(f"\nDuration : {session.duration_minutes} min\n")
    p.text(f"Started  : {start_label}\n")
    p.text(f"Ends at  : {end_label}\n\n")
    p.text("Progress :\n")
    p.text(f"{progress_bar(0.0)}\n")
    p.text("  0% — Lock in. Let's go.\n")
    if streak > 0:
        p.text(f"\nSTREAK   : {streak} sessions\n")
    print_centered(p, "================================")
    p.text("\n\n")
    p.cut()
    p.close()


def print_update_receipt(session: FocusSession, update_num: int, pct: int, remaining_min: int) -> None:
    p = get_printer()
    if not p:
        return

    ratio = pct / 100.0
    quote = get_random_quote()

    p.text("\n")
    print_centered(p, "================================")
    print_centered(p, f"   UPDATE #{update_num} — {pct}%")
    print_centered(p, "================================")
    p.text("\n")
    p.set(align="left", font="a", bold=False)
    p.text("TASK:\n")
    wrap_text(p, f'"{session.task}"')
    p.text("\nProgress :\n")
    p.text(f"{progress_bar(ratio)}\n")
    elapsed_min = session.duration_minutes - remaining_min
    p.text(f"  {elapsed_min} min done | {remaining_min} min left\n\n")

    p.set(align="left", font="a", bold=False)
    p.text(f"> {quote} <\n")

    print_centered(p, "================================")
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
    level: int | None = None,
    total_xp: int | None = None,
    daily_streak: int | None = None,
    new_records: list[str] | None = None,
) -> None:
    p = get_printer()
    if not p:
        return

    end_time = datetime.now()
    start_label = session.start_clock.strftime("%H:%M")
    end_label = end_time.strftime("%H:%M")
    time_bonus = get_time_bonus()
    flavor = get_random_quote()
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
    p.text(f"TOTAL:  {total_sessions} sessions / {hours} hrs\n")
    if level is not None and total_xp is not None:
        p.text(f"LEVEL:  {level} ({total_xp} XP)\n")
    if daily_streak:
        p.text(f"DAY STREAK: {daily_streak}\n")
    if new_records:
        print_new_record_lines(p, new_records)
    p.text(f'\n> {flavor} <\n')
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
        try:
            log_focus_session(
                event_type="focus_partial",
                task=session.task,
                duration_minutes=session.duration_minutes,
                elapsed_minutes=elapsed,
                xp=xp,
                tier=tier,
            )
        except Exception as e:
            print(f"Database error: {e}")
    else:
        print("\n\nSession abandoned.")
        print_abandoned_receipt(session)
        try:
            log_focus_session(
                event_type="focus_abandoned",
                task=session.task,
                duration_minutes=session.duration_minutes,
                elapsed_minutes=elapsed,
                xp=0,
                tier="common",
            )
        except Exception as e:
            print(f"Database error: {e}")

    sys.exit(0)


def run_timer(session: FocusSession) -> None:
    total_seconds = session.duration_minutes * 60
    t1_seconds = total_seconds / 3.0
    t2_seconds = (total_seconds * 2.0) / 3.0

    while True:
        elapsed_seconds = time.monotonic() - session.start_monotonic
        remaining = total_seconds - elapsed_seconds

        if remaining <= 0:
            break

        if session.checkin_enabled:
            if not session.update_1_done and elapsed_seconds >= t1_seconds:
                remaining_min = max(1, int(round((total_seconds - elapsed_seconds) / 60)))
                print("\n\nProgress Update 1 (33%) — printing receipt...")
                print_update_receipt(session, update_num=1, pct=33, remaining_min=remaining_min)
                session.update_1_done = True

            elif not session.update_2_done and elapsed_seconds >= t2_seconds:
                remaining_min = max(1, int(round((total_seconds - elapsed_seconds) / 60)))
                print("\n\nProgress Update 2 (67%) — printing receipt...")
                print_update_receipt(session, update_num=2, pct=67, remaining_min=remaining_min)
                session.update_2_done = True

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
        "--no-updates",
        "--no-checkin",
        action="store_true",
        dest="no_updates",
        help="Disable mid-session status update receipts (at 1/3 and 2/3)",
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
        checkin_enabled=not args.no_updates,
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

    db_result: dict = {}
    try:
        db_result = log_focus_session(
            event_type="focus_complete",
            task=session.task,
            duration_minutes=session.duration_minutes,
            elapsed_minutes=session.duration_minutes,
            xp=xp,
            tier=tier,
        )
    except Exception as e:
        print(f"Database error: {e}")
        db_result = streak_state

    print_session_complete_receipt(
        session,
        xp=xp,
        streak=int(
            db_result.get(
                "current_focus_streak",
                streak_state.get("current_streak", 0),
            )
        ),
        streak_increased=bool(db_result.get("focus_streak_increased")),
        total_sessions=int(
            db_result.get(
                "total_focus_sessions",
                streak_state.get("total_sessions", 0),
            )
        ),
        total_minutes=int(
            db_result.get(
                "total_focus_minutes",
                streak_state.get("total_minutes", 0),
            )
        ),
        level=db_result.get("level"),
        total_xp=db_result.get("total_xp"),
        daily_streak=db_result.get("daily_streak"),
        new_records=db_result.get("new_records"),
    )

    if db_result.get("leveled_up"):
        print_level_up_receipt(
            db_result["old_level"],
            db_result["level"],
            db_result["total_xp"],
        )

    if args.complete:
        complete_todoist_task(session.task)

    return 0


if __name__ == "__main__":
    sys.exit(main())
