import random
from fastapi import FastAPI, Request, HTTPException
from util import *
import print_todos
import textwrap
from datetime import datetime

app = FastAPI()

REWARDS = {
    "common": [
        "XP GAINED: +50",
        "XP GAINED: +75",
        "PROGRESS +10%",
        "STAMINA RESTORED",
    ],
    "rare": [
        "XP GAINED: +150",
        "*** CRITICAL HIT! ***",
        "DOUBLE XP BONUS",
        "LEVEL UP!",
    ],
    "epic": [
        "XP GAINED: +300",
        "*** TRIPLE COMBO ***",
        "ACHIEVEMENT UNLOCKED",
        "LEGENDARY STREAK!",
    ],
    "legendary": [
        "*** ULTRA RARE! ***",
        "*** MASTER ACHIEVER ***",
        "*** GODLIKE STATUS ***",
    ]
}

QUOTES = [
    "One step closer.",
    "Glitch in matrix fixed.",
    "Compiling success...",
    "Deploying satisfaction.",
    "Ticket closed.",
    "Bug squashed. Life.exe continues.",
    "Commit pushed to reality.",
    "Achievement unlocked: Discipline.",
    "Return on investment: Infinite.",
    "Stack trace: cleared.",
]

ASCII_FRAMES = [
    ["  /\\_/\\  ", " ( o.o ) ", "  > ^ <  "],
    ["  ^___^  ", " ( ^_^ ) ", "  /   \\  "],
    ["  * * *  ", "  \\_O_/  ", "   | |   "],
    ["  * * *  ", " +-----+ ", " |EPIC!| "],
]


def get_reward_tier():
    """Randomly select reward tier with weighted probabilities."""
    roll = random.random()
    if roll < 0.60:
        return "common"
    elif roll < 0.85:
        return "rare"
    elif roll < 0.97:
        return "epic"
    else:
        return "legendary"


def print_ascii_art(p, frame):
    """Print ASCII art centered."""
    p.set(align="center", font="b")
    for line in frame:
        p.text(f"{line}\n")


def get_time_bonus():
    """Get bonus text based on time of day."""
    hour = datetime.now().hour
    if 5 <= hour < 9:
        return "+ EARLY BIRD BONUS"
    elif 9 <= hour < 12:
        return "+ MORNING WARRIOR"
    elif 12 <= hour < 14:
        return "+ LUNCH BREAK HERO"
    elif 14 <= hour < 18:
        return "+ AFTERNOON GRIND"
    elif 18 <= hour < 22:
        return "+ NIGHT OWL POWER"
    else:
        return "+ MIDNIGHT LEGEND"


def beep(p):
    try:
        p.cashdraw(2)
    except:
        print("wala man")
        pass

    p._raw(b"\x1b\x42\x03\x01")


@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get("event_name") == "item:completed":
        task_content = data["event_data"]["content"]
        if "task print" in task_content.lower():
            print_todos.main()
        else:
            print_reward(task_content)

    return {"status": "ok"}


def print_reward(task_name):
    p = get_printer()
    
    if not p:
        return

    available_width = MAX_WIDTH - 4
    
    tier = get_reward_tier()
    reward_text = random.choice(REWARDS[tier])
    flavor_text = random.choice(QUOTES)
    time_bonus = get_time_bonus()
    ascii_frame = random.choice(ASCII_FRAMES)
    
    wrapped_task_name = textwrap.wrap(task_name, width=available_width)

    beep(p)

    p.text("\n")
    p.set(bold=True, align="center", font="a")
    p.text(f"=== {datetime.now().strftime('%Y-%m-%d')} ===\n")
    p.set(bold=False)
    
    p.set(bold=True, align="center", font="a")
    tier_display = tier.upper()
    if tier == "legendary":
        p.text(f"+==============================+\n")
        p.text(f"|  *** {tier_display} ***  |\n")
        p.text(f"+==============================+\n")
    elif tier == "epic":
        p.text(f"+------------------------------+\n")
        p.text(f"| * {tier_display} REWARD * |\n")
        p.text(f"+------------------------------+\n")
    elif tier == "rare":
        p.text(f"+----------------------------+\n")
        p.text(f"|   * {tier_display} *   |\n")
        p.text(f"+----------------------------+\n")
    
    print_ascii_art(p, ascii_frame)
    
    p.set(bold=True, align="center", font="b")
    p.text("--------------------------------\n")
    p.text("[X] TASK COMPLETED [X]\n")
    p.set(bold=False, align="center", font="b")
    for line in wrapped_task_name:
        p.text(f"{line.title()}\n")
    
    p.set(bold=True, align="center", font="a")
    p.text("--------------------------------\n")
    p.text(f"{reward_text}\n")
    p.text("--------------------------------\n")
    
    p.set(bold=False, font="b", align="center")
    p.text(f"{time_bonus}\n")
    
    p.set(bold=False, font="b", align="center")
    p.text(f"\n> {flavor_text} <\n")
    
    p.text("--------------------------------\n")
    p.text("\n\n")

    p.cut()
    p.close()


if __name__ == "__main__":
    p = get_printer()
    beep(p)
