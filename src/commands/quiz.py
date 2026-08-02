"""
quiz.py — Quiz Daemon

Runs in the background and prints quiz receipts on a configurable schedule:
  - Warning slip 30 minutes before each quiz
  - Question slip at the scheduled time (popped from the pre-generated pool)
  - Answer slip after a configurable delay (unless already answered manually)

Usage:
    python -m src.commands.quiz
    python -m src.commands.quiz --interval 60 --answer-delay 10
    python -m src.commands.quiz --once
    python -m src.commands.quiz --no-warning
"""

from __future__ import annotations

import argparse
import signal
import sys
import textwrap
import time
from datetime import datetime, timedelta

from src.config import MAX_WIDTH, QUIZ_ANSWER_DELAY, QUIZ_INTERVAL, QUIZ_TOPIC
from src.db import (
    count_quiz_pool,
    get_pending_quiz,
    mark_quiz_answered,
    pop_next_quiz,
)
from src.printer import get_printer, print_centered

# ---------------------------------------------------------------------------
# Receipt printing helpers
# ---------------------------------------------------------------------------

SEPARATOR = "-" * MAX_WIDTH
THICK_SEP = "=" * MAX_WIDTH

_quiz_counter = 0  # increments each session; not persisted (resets on daemon restart)


def _wrap(text: str, indent: str = "") -> list[str]:
    """Wrap text to MAX_WIDTH with optional indent."""
    available = MAX_WIDTH - len(indent)
    return textwrap.wrap(text, width=available) or [text[:available]]


def print_warning_slip(p, quiz_time: datetime, topic: str) -> None:
    """Print the '30 minutes until quiz' warning receipt."""
    time_str = quiz_time.strftime("%-I:%M%p").lower()
    date_str = quiz_time.strftime("%m-%d-%y")

    p.text("\n")
    print_centered(p, THICK_SEP)
    p.set(align="center", bold=True, font="a")
    p.text("!!! QUIZ INCOMING !!!\n")
    p.set(align="center", bold=False, font="a")
    p.text(f"Next quiz at {time_str}  {date_str}\n")
    p.text(f"Topic: {topic}\n")
    p.text("\n")
    p.set(align="center", bold=True, font="a")
    p.text("Prep your brain.\n")
    p.set(align="left", bold=False, font="a")
    print_centered(p, THICK_SEP)
    p.text("\n\n")
    p.cut()


def print_question_slip(p, quiz: dict, quiz_num: int, answer_delay: int) -> None:
    """Print the question receipt."""
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    question = quiz["question"]

    p.text("\n")
    print_centered(p, THICK_SEP)
    p.set(align="center", bold=True, font="a")
    p.text(f"QUIZ TIME  #{quiz_num}\n")
    p.set(align="center", bold=False, font="a")
    p.text(f"{now_str}\n")
    print_centered(p, THICK_SEP)
    p.text("\n")

    # Question body
    p.set(align="left", bold=True, font="a")
    p.text("Q: ")
    p.set(bold=False)
    lines = _wrap(question)
    p.text(f"{lines[0]}\n")
    for line in lines[1:]:
        p.text(f"   {line}\n")

    p.text("\n")
    p.set(align="center", bold=False, font="a")
    p.text("[ Write your answer below ]\n")
    p.text("\n\n\n")
    p.set(align="left")
    p.text(" X _____________________________\n")
    p.text("\n")
    p.set(align="center", bold=False, font="a")
    p.text(f"Answer prints in {answer_delay} min.\n")
    p.text("Or run: python -m src.commands.quiz_answer\n")
    print_centered(p, THICK_SEP)
    p.text("\n\n")
    p.cut()


def print_answer_slip(p, quiz: dict, quiz_num: int) -> None:
    """Print the answer receipt."""
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    question = quiz["question"]
    answer = quiz["answer"]
    source = quiz.get("source_file") or "Unknown source"

    p.text("\n")
    print_centered(p, THICK_SEP)
    p.set(align="center", bold=True, font="a")
    p.text(f"ANSWER  #{quiz_num}\n")
    p.set(align="center", bold=False, font="a")
    p.text(f"{now_str}\n")
    print_centered(p, THICK_SEP)
    p.text("\n")

    # Repeat condensed question
    p.set(align="left", bold=True, font="a")
    p.text("Q: ")
    p.set(bold=False)
    q_lines = _wrap(question)
    p.text(f"{q_lines[0]}\n")
    for line in q_lines[1:]:
        p.text(f"   {line}\n")
    p.text("\n")

    # Answer
    p.set(align="left", bold=True, font="a")
    p.text("A: ")
    p.set(bold=False)
    a_lines = _wrap(answer)
    p.text(f"{a_lines[0]}\n")
    for line in a_lines[1:]:
        p.text(f"   {line}\n")

    p.text("\n")
    p.set(align="center", bold=False, font="a")
    # Trim source path to filename only for display
    from pathlib import Path as _Path
    src_name = _Path(source).name if source != "Unknown source" else source
    p.text(f"Source: {src_name}\n")
    print_centered(p, THICK_SEP)
    p.text("\n\n")
    p.cut()


def print_pool_empty_slip(p) -> None:
    """Print a 'pool exhausted' slip so the daemon doesn't silently fail."""
    p.text("\n")
    print_centered(p, THICK_SEP)
    p.set(align="center", bold=True, font="a")
    p.text("QUIZ POOL EMPTY\n")
    p.set(align="center", bold=False, font="a")
    p.text("Re-run quiz_ingest to\n")
    p.text("generate more questions.\n")
    print_centered(p, THICK_SEP)
    p.text("\n\n")
    p.cut()


# ---------------------------------------------------------------------------
# Core quiz cycle
# ---------------------------------------------------------------------------

def run_quiz_cycle(interval_min: int, answer_delay_min: int, warn: bool, topic: str) -> None:
    """Execute one full quiz cycle: pop question, print, wait, print answer."""
    global _quiz_counter

    # Pop from pool
    quiz = pop_next_quiz()
    if quiz is None:
        print(f"[{_ts()}] Quiz pool empty — printing notice slip.")
        p = get_printer()
        if p:
            print_pool_empty_slip(p)
            p.close()
        return

    _quiz_counter += 1
    history_id = quiz["history_id"]
    quiz_num = _quiz_counter

    remaining = count_quiz_pool()
    if remaining < 5:
        print(
            f"[{_ts()}] WARNING: Quiz pool running low ({remaining} remaining). "
            f"Re-run quiz_ingest to refill."
        )

    print(f"[{_ts()}] Printing question #{quiz_num}...")
    p = get_printer()
    if p:
        print_question_slip(p, quiz, quiz_num, answer_delay_min)
        p.close()

    # Wait for answer delay, checking for manual answer every 5 seconds
    wait_seconds = answer_delay_min * 60
    elapsed = 0
    check_interval = 5

    print(f"[{_ts()}] Waiting {answer_delay_min} min for answer...")
    while elapsed < wait_seconds:
        time.sleep(min(check_interval, wait_seconds - elapsed))
        elapsed += check_interval

        # Check if user already answered manually
        pending = get_pending_quiz()
        if pending is None or pending.get("id") != history_id:
            print(f"[{_ts()}] Question #{quiz_num} already answered manually. Skipping answer slip.")
            return

    # Print answer slip (only if not already answered)
    pending = get_pending_quiz()
    if pending is not None and pending.get("id") == history_id:
        print(f"[{_ts()}] Printing answer #{quiz_num}...")
        p = get_printer()
        if p:
            quiz["source_file"] = pending.get("source_file")
            print_answer_slip(p, quiz, quiz_num)
            p.close()
        mark_quiz_answered(history_id)
    else:
        print(f"[{_ts()}] Question #{quiz_num} was answered manually before answer slip.")


# ---------------------------------------------------------------------------
# Scheduler loop
# ---------------------------------------------------------------------------

def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def run_daemon(
    interval_min: int,
    answer_delay_min: int,
    warn: bool,
    topic: str,
) -> None:
    """Main scheduling loop. Blocks forever."""
    print(
        f"Quiz daemon started. "
        f"Interval: {interval_min} min | "
        f"Answer delay: {answer_delay_min} min | "
        f"Topic: {topic}"
    )
    print(f"Pool size: {count_quiz_pool()} pending questions")
    print("Press Ctrl+C to stop.\n")

    while True:
        next_quiz_time = datetime.now() + timedelta(minutes=interval_min)
        warn_time = next_quiz_time - timedelta(minutes=30)

        print(f"[{_ts()}] Next quiz at {next_quiz_time.strftime('%H:%M')} "
              f"({interval_min} min from now)")

        # Sleep until warning time or quiz time
        now = datetime.now()
        if warn and warn_time > now and interval_min > 35:
            # Sleep until 30-min warning
            sleep_until(warn_time)

            # Print warning slip
            print(f"[{_ts()}] Printing 30-min warning slip...")
            p = get_printer()
            if p:
                try:
                    print_warning_slip(p, next_quiz_time, topic)
                    p.close()
                except Exception as e:
                    print(f"[{_ts()}] Warning slip error: {e}")

            # Sleep until quiz time
            sleep_until(next_quiz_time)
        else:
            # No warning (interval too short) — sleep straight to quiz time
            sleep_until(next_quiz_time)

        # Run the quiz cycle
        try:
            run_quiz_cycle(interval_min, answer_delay_min, warn, topic)
        except Exception as e:
            print(f"[{_ts()}] Quiz cycle error: {e}")


def sleep_until(target: datetime) -> None:
    """Sleep until a target datetime, handling minor clock drift."""
    while True:
        remaining = (target - datetime.now()).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30))


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _handle_sigterm(signum, frame):
    print(f"\n[{_ts()}] Quiz daemon stopped (SIGTERM).")
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Quiz daemon — prints study Q&A receipts on a schedule"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=QUIZ_INTERVAL,
        metavar="MINUTES",
        help=f"Minutes between quizzes (default: {QUIZ_INTERVAL})",
    )
    parser.add_argument(
        "--answer-delay",
        type=int,
        default=QUIZ_ANSWER_DELAY,
        dest="answer_delay",
        metavar="MINUTES",
        help=f"Minutes after question before answer prints (default: {QUIZ_ANSWER_DELAY})",
    )
    parser.add_argument(
        "--topic",
        default=QUIZ_TOPIC,
        help=f"Topic shown on warning slips (default: '{QUIZ_TOPIC}')",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Fire one quiz immediately and exit (no scheduling)",
    )
    parser.add_argument(
        "--no-warning",
        action="store_true",
        dest="no_warning",
        help="Skip the 30-minute warning slip",
    )
    args = parser.parse_args(argv)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    if count_quiz_pool() == 0:
        print(
            "Warning: Quiz pool is empty. Run quiz_ingest first.\n"
            "  python -m src.commands.quiz_ingest /path/to/notes.pdf"
        )
        if not args.once:
            print("Daemon will start but can only print 'pool empty' slips.")

    if args.once:
        print("Running one quiz cycle...")
        try:
            run_quiz_cycle(
                interval_min=args.interval,
                answer_delay_min=args.answer_delay,
                warn=not args.no_warning,
                topic=args.topic,
            )
        except KeyboardInterrupt:
            print("\nInterrupted.")
        return

    try:
        run_daemon(
            interval_min=args.interval,
            answer_delay_min=args.answer_delay,
            warn=not args.no_warning,
            topic=args.topic,
        )
    except KeyboardInterrupt:
        print(f"\n[{_ts()}] Quiz daemon stopped.")


if __name__ == "__main__":
    main()
