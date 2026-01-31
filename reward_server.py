import random
from fastapi import FastAPI, Request, HTTPException
from util import *

app = FastAPI()

REWARDS = [
    "XP GAINED: +150",
    "XP GAINED: +200",
    "  CRITICAL HIT!  ",
    "  COMBO STREAK!  ",
    "  SYSTEM UPGRADE ",
    " DOPAMINE: HIGH  ",
]

QUOTES = [
    "One step closer.",
    "Glitch in matrix fixed.",
    "Compiling success...",
    "Deploying satisfaction.",
    "Ticket closed.",
]


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
        print_reward(task_content)

    return {"status": "ok"}


def print_reward(task_name):
    p = get_printer()
    
    if not p:
        return

    main_reward = random.choice(REWARDS)
    flavor_text = random.choice(QUOTES)

    beep(p)

    p.set(align="center", bold=True)

    p.text("\n")
    p.text("################################")

    p.set(bold=False, align="center", font="b")
    p.text(f"COMPLETED:\n{task_name[:30]}\n")

    p.set(bold=True, align="center", font="a")
    p.text("--------------------------------")
    p.text(f"\n{main_reward}\n\n")
    p.text("--------------------------------")

    p.set(bold=False, font="b")
    p.text(f"{flavor_text}\n")

    p.text("################################")
    p.text("\n\n")

    p.cut()

    p.close()


if __name__ == "__main__":
    p = get_printer()
    beep(p)
