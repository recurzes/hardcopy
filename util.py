from dotenv import load_dotenv
from escpos.printer import Usb
import os
import time

load_dotenv()

TODOIST_API_KEY = os.getenv("TODOIST_API_KEY")
VENDOR_ID = 0x483
PRODUCT_ID = 0x070B
MAX_WIDTH = 32

def get_printer(max_retries=3, retry_delay=1) -> Usb | None:
    """Get printer with retry logic for busy resource."""
    for attempt in range(max_retries):
        try:
            printer = Usb(VENDOR_ID, PRODUCT_ID, timeout=0, profile="TM-T88III", unbind_active_driver=True)
            return printer
        except Exception as e:
            if "busy" in str(e).lower() and attempt < max_retries - 1:
                print(f"Printer busy, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"Printer Error: {e}")
                if attempt == max_retries - 1:
                    return None
    return None

def print_centered(p, text):
    p.set(align='center', bold=True)
    p.text(text + "\n")
    p.set(align='left', bold=False)