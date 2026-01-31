from dotenv import load_dotenv
from escpos.printer import Usb
import os

load_dotenv()

TODOIST_API_KEY = os.getenv("TODOIST_API_KEY")
VENDOR_ID = 0x483
PRODUCT_ID = 0x070B
MAX_WIDTH = 32

def get_printer() -> Usb | None:
    try:
        return Usb(VENDOR_ID, PRODUCT_ID, 0, profile="TM-T88III")
    except Exception as e:
        print(f"Printer Error: {e}")
        return None