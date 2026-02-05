from datetime import datetime
import textwrap
from util import *

HABITS = [
    "Drink 1-2 Liters of Water",
    "Morning Coffee",
    "Read Book",
    "Work Future Business",
    "Study Cybersecurity",
    "Clean Room",
    "Sleep Early",
    "Walk Outside"
]

def print_centered(p, text):
    p.set(align='center', bold=True)
    p.text(text + "\n")
    p.set(align='left', bold=False)
    
def print_habit(p, content):
    available_width = MAX_WIDTH - 4
    wrapped_lines = textwrap.wrap(content, width=available_width)
    
    if wrapped_lines:
        p.text(f"[ ] {wrapped_lines[0]}\n")
        
        for line in wrapped_lines[1:]:
            p.text(f"    {line}\n")
    
    else:
        p.text("[ ] ???\n")
        
def main():
    try:
        p = get_printer()
        
        if not p:
            return
        
        p.text("\n")
        print_centered(p, f"{datetime.now().strftime("%Y-%m-%d")}")
        print_centered(p, "================================")
        print_centered(p, "    HABITS TO WORK ON    ")
        print_centered(p, "================================")
        
        p.set(align='left', font='a')
        
        for habit in HABITS:
            print_habit(p, habit)
            
        p.text("\n")
        p.text("--------------------------------\n")
        p.set(align='center', bold=True)
        p.text("Bitchass Go Do This.\n")
        p.set(align='left', bold=False)
        p.text("\n\n\n")
        p.cut()
    
    except Exception as e:
        print(f"Error: {e}")
        print("Tip: Check if the printer is connected and permissions are set")
        

if __name__ == "__main__":
    main()