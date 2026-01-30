from fastapi import FastAPI, Request
from escpos.printer import Usb

app = FastAPI()

# Run `lsusb` in terminal to get the vendor id and product id
printer = Usb()


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
