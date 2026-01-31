import textwrap
from datetime import datetime
from todoist_api_python.api import TodoistAPI
from escpos.printer import Usb
from dotenv import load_dotenv
import os
from datetime import date
from pathlib import Path

load_dotenv()
# Config
todoist_api = os.getenv("TODOIST_API_KEY")

VENDOR_ID = 0x483
PRODUCT_ID = 0x070B

MAX_WIDTH = 32

def print_centered(p, text):
    p.set(align='center', bold=True)
    p.text(text + "\n")
    p.set(align='left', bold=False)


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
        if not todoist_api:
            print("TODOIST_API_KEY not set in environment variables.")
            return

        api = TodoistAPI(todoist_api)
        p = Usb(VENDOR_ID, PRODUCT_ID, 0, profile='TM-T88III')

        all_tasks = api.get_tasks(limit=10)
        task_to_print = []

        for page in all_tasks:
            for task in page:
                task_to_print.append(task)

        if not task_to_print:
            print("No tasks for today! Enjoy your freedom")
            return
        
        p.text('\n')
        print_centered(p, "================================")
        print_centered(p, "    DAILY QUEST LOG    ")
        print_centered(p, datetime.now().strftime("%Y-%m-%d"))
        print_centered(p, "================================")

        p.set(align='left', font='a')

        for task in task_to_print:
            print_task_item(p, task.content)

        p.text("\n")
        p.text("--------------------------------\n")
        p.set(align='center', bold=True)
        p.text("I commit to these tasks.\n")
        p.set(align='left', bold=False)
        p.text("\n\n\n")
        p.text(" X ___________________________\n")
        p.text("          (Signature)\n")
        p.text("\n\n")

        p.cut()
        print(f"Successfully printed {len(task_to_print)} tasks")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Tip: Check if the printer is connected and permissions are set.")


if __name__ == "__main__":
    main()