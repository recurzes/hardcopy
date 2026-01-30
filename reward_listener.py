from fastapi import FastAPI, Request
from escpos.printer import Usb

app = FastAPI()

# Run `lsusb` in terminal to get the vendor id and product id
VENDOR_ID = 0x483
PRODUCT_ID = 0x070B
printer = Usb(VENDOR_ID, PRODUCT_ID, 0, profile="TM-T88III")


@app.post("/webhook")
async def handle_todoist_hook(request: Request):
    data = await request.json()

    if data["event_name"] == "item:completed":
        task_content = data["event_data"]["content"]

        # The Dopamine Hit
        printer.text("\n")
        printer.text("--------------------------------\n")
        printer.text(f"   TASK CRUSHED: {task_content}\n")
        printer.text("--------------------------------\n")
        printer.text("       +100 DOPAMINE POINTS     \n")
        printer.text("--------------------------------\n")
        printer.cut()

    return {"status": "ok"}
