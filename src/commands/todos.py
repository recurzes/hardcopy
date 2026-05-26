import textwrap
from datetime import datetime

from todoist_api_python.api import TodoistAPI

from src.config import MAX_WIDTH, TODOIST_API_KEY
from src.printer import get_printer, print_centered


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


def main():
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
