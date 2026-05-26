from src.commands.reward import beep
from src.printer import get_printer
from src.server import app

if __name__ == "__main__":
    p = get_printer()
    if p:
        beep(p)
        p.close()
    else:
        print("No printer available for test beep.")
