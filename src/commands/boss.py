from datetime import datetime, timedelta

from escpos.printer import Usb
from todoist_api_python.api import TodoistAPI

from src.config import TODOIST_API_KEY
from src.db import compute_boss_rank, get_weekly_history, log_boss_fight
from src.printer import get_printer

XP_PER_TASK = 100
WEEKLY_GOAL_TASKS = 20
BOSS_HEALTH = WEEKLY_GOAL_TASKS * XP_PER_TASK


def print_boss_art(p: Usb, defeated=True):
    p.set(align="center", bold=True)
    if defeated:
        p.text("\n")
        p.text("      .+.      \n")
        p.text("    (  |  )    \n")
        p.text("     |   |     \n")
        p.text("     `---'     \n")
        p.text("  BOSS DEFEATED \n")
    else:
        p.text("\n")
        p.text("     (o.o)     \n")
        p.text("      |=|      \n")
        p.text("     __|__     \n")
        p.text("  BOSS SURVIVED \n")
    p.text("\n")


def format_trend_line(history: list[dict]) -> str:
    ranks = []
    for week in history:
        rank = week.get("rank")
        if rank:
            ranks.append(rank)
        elif week.get("tasks_completed", 0) > 0:
            ranks.append(compute_boss_rank(week["tasks_completed"], WEEKLY_GOAL_TASKS))
        else:
            ranks.append("-")
    return " -> ".join(ranks)


def winning_streak_weeks(history: list[dict]) -> int:
    streak = 0
    for week in reversed(history):
        if week.get("defeated"):
            streak += 1
        elif week.get("rank") in ("A", "S+"):
            streak += 1
        else:
            break
    return streak


def improvement_note(history: list[dict]) -> str | None:
    if len(history) < 2:
        return None

    current = history[-1].get("tasks_completed", 0)
    previous = history[-2].get("tasks_completed", 0)
    if previous <= 0 or current <= previous:
        return None

    pct = round(((current - previous) / previous) * 100)
    return f"TASKS UP {pct}% FROM LAST WEEK"


def main():
    try:
        if not TODOIST_API_KEY:
            print("TODOIST_API_KEY not set in environment variables.")
            return

        api = TodoistAPI(TODOIST_API_KEY)
        p = get_printer()

        if not p:
            return

        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        completed_tasks = []
        for page in api.get_completed_tasks_by_completion_date(
            since=start_date, until=end_date
        ):
            completed_tasks.extend(page)

        total_tasks = len(completed_tasks)
        total_xp = total_tasks * XP_PER_TASK
        boss_defeated = total_tasks >= WEEKLY_GOAL_TASKS
        rank = compute_boss_rank(total_tasks, WEEKLY_GOAL_TASKS)

        history = get_weekly_history(weeks=4)
        trend_line = format_trend_line(history)
        win_streak = winning_streak_weeks(history)
        improvement = improvement_note(history)

        p.set(align="center", bold=True, double_height=True)
        p.text("WEEKLY RAID REPORT\n")
        p.set(double_height=False, font="b")
        p.text(f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}\n")
        p.text("--------------------------------")

        print_boss_art(p, defeated=boss_defeated)

        p.set(align="center", bold=True, double_width=True, double_height=True)
        p.text(f"RANK: {rank}\n")

        p.set(double_width=False, double_height=False, font="b")
        p.text(f"\nTasks: {total_tasks} / {WEEKLY_GOAL_TASKS}\n")
        p.text(f"XP: {total_xp}\n\n")

        if trend_line:
            p.text("4-WEEK TREND:\n")
            p.text(f"{trend_line}\n\n")

        if win_streak >= 2:
            p.text(f"{win_streak}-WEEK WINNING STREAK!\n\n")

        if improvement:
            p.text(f"{improvement}\n\n")

        p.set(align="center", bold=True)
        if boss_defeated:
            p.text("REWARD UNLOCKED:\n")
            p.text("[ ] Treat yourself to a meal\n")
            p.text("[ ] 1 Hour guilt-free gaming\n")
        else:
            p.text("PENALTY:\n")
            p.text("[ ] Review next week's plan\n")
            p.text("[ ] Clean desk space\n")

        p.text("\n\n\n")
        p.cut()
        p.close()

        try:
            log_boss_fight(
                rank=rank,
                tasks_completed=total_tasks,
                defeated=boss_defeated,
                total_xp=total_xp,
            )
        except Exception as e:
            print(f"Database error: {e}")

        print(f"Weekly Raid Report Printed: {total_tasks} tasks completed.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
