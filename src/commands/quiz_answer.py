"""
quiz_answer.py — Manual Answer Trigger

Prints the answer slip for the currently pending quiz question immediately,
without waiting for the scheduled delay. The daemon will see the 'answered'
status and skip its own answer slip for that question.

Usage:
    python -m src.commands.quiz_answer           # print current pending answer
    python -m src.commands.quiz_answer --id 7    # reprint a specific past answer
    python -m src.commands.quiz_answer --history  # list recent quiz history
"""

from __future__ import annotations

import argparse
import textwrap
from datetime import datetime
from pathlib import Path

from src.config import MAX_WIDTH
from src.db import get_pending_quiz, get_quiz_by_id, get_quiz_history, mark_quiz_answered
from src.printer import get_printer, print_centered

THICK_SEP = "=" * MAX_WIDTH


def _wrap(text: str) -> list[str]:
    return textwrap.wrap(text, width=MAX_WIDTH - 3) or [text[: MAX_WIDTH - 3]]


def print_answer_slip(p, quiz: dict, quiz_id: int) -> None:
    """Print a full answer receipt."""
    now_str = datetime.now().strftime("%Y-%m-%d  %H:%M")
    question = quiz.get("question", "")
    answer = quiz.get("answer", "")
    source = quiz.get("source_file") or "Unknown"

    p.text("\n")
    print_centered(p, THICK_SEP)
    p.set(align="center", bold=True, font="a")
    p.text(f"ANSWER  #{quiz_id}\n")
    p.set(align="center", bold=False, font="a")
    p.text(f"{now_str}\n")
    print_centered(p, THICK_SEP)
    p.text("\n")

    # Question recap
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
    src_name = Path(source).name if source != "Unknown" else source
    p.text(f"Source: {src_name}\n")
    print_centered(p, THICK_SEP)
    p.text("\n\n")
    p.cut()


def show_history(limit: int = 10) -> None:
    """Print a table of recent quiz history to the terminal."""
    rows = get_quiz_history(limit)
    if not rows:
        print("No quiz history found.")
        return

    print(f"\n{'#':<4}  {'Status':<18}  {'Asked At':<17}  Question")
    print("-" * 78)
    for r in rows:
        q_preview = (r["question"][:45] + "...") if len(r["question"]) > 45 else r["question"]
        status = r["status"]
        asked = r["asked_at"][:16] if r["asked_at"] else "-"
        print(f"{r['id']:<4}  {status:<18}  {asked:<17}  {q_preview}")
    print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Print the answer for a pending or past quiz question"
    )
    parser.add_argument(
        "--id",
        type=int,
        default=None,
        metavar="N",
        help="Print the answer for a specific quiz history ID (for review)",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="List recent quiz history in the terminal and exit",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of history entries to show (default: 10)",
    )
    args = parser.parse_args(argv)

    # -- --history -----------------------------------------------------------
    if args.history:
        show_history(limit=args.limit)
        return

    # -- --id N: print a specific past answer --------------------------------
    if args.id is not None:
        quiz = get_quiz_by_id(args.id)
        if not quiz:
            print(f"No quiz found with ID {args.id}.")
            return
        p = get_printer()
        if not p:
            return
        try:
            print(f"Reprinting answer for quiz #{args.id}...")
            print_answer_slip(p, quiz, args.id)
            p.close()
            print("Done.")
        except Exception as e:
            print(f"Printer error: {e}")
        return

    # -- Default: print current pending answer -------------------------------
    quiz = get_pending_quiz()
    if not quiz:
        print(
            "No active quiz question found.\n"
            "Run the daemon or trigger one with: python -m src.commands.quiz --once"
        )
        return

    history_id = quiz["id"]
    p = get_printer()
    if not p:
        return

    try:
        print(f"Printing answer for quiz #{history_id}...")
        print_answer_slip(p, quiz, history_id)
        p.close()
        mark_quiz_answered(history_id)
        print("Done. The scheduled answer slip will be skipped by the daemon.")
    except Exception as e:
        print(f"Printer error: {e}")
        print("Tip: Check if the printer is connected and permissions are set.")


if __name__ == "__main__":
    main()
