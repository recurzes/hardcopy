from datetime import datetime, timedelta

from escpos.printer import Usb
from todoist_api_python.api import TodoistAPI

from src.config import TODOIST_API_KEY
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

        p.set(align="center", bold=True, double_height=True)
        p.text("WEEKLY RAID REPORT\n")
        p.set(double_height=False, font="b")
        p.text(f"{start_date.strftime('%b %d')} - {end_date.strftime('%b %d')}\n")
        p.text("--------------------------------")

        print_boss_art(p, defeated=boss_defeated)

        p.set(align="center", bold=True, double_width=True, double_height=True)
        if total_xp >= BOSS_HEALTH * 1.5:
            p.text("RANK: S+\n")
        elif boss_defeated:
            p.text("RANK: A\n")
        elif total_xp >= BOSS_HEALTH * 0.5:
            p.text("RANK: C\n")
        else:
            p.text("RANK: F\n")

        p.set(double_width=False, double_height=False, font="b")
        p.text("\n")
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

        print(f"Weekly Raid Report Printed: {total_tasks} tasks completed.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
