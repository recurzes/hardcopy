# HARDCOPY
**Physicalizing Productivity for the Dopamine-Starved Brain.**

Hardcopy turns your abstract Todoist list into a physical reality. Inspired by the work of [Coding with Lewis](https://www.youtube.com/@CodingWithLewis), this project utilizes a thermal receipt printer to create daily "contracts" and real-time "reward slips" to gamify the workflow of software developers and power users.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg) ![Arch Linux](https://img.shields.io/badge/OS-Arch%20Linux-1793d1.svg) ![Hardware](https://img.shields.io/badge/Hardware-Thermal%20Printer-black.svg)

## System Architecture

The system operates on threee distinct modules:

1. **The Contract (Morning):** Fetches "Today's" tasks and prints a physical checklist to sign.
2. **The Daemon (All Day):** A local FastAPI server listening to Todoist Webhooks. When a task is checked off digitally, the printer immediately prints a randomized "XP Reward" slip.
3. **The Boss Fight (Weekly):** A Sunday night summary that calculates total XP, determines if you "defeated" the week, and prints a rank (S+ to F).


## Hardware Requirements

- **Host:** Linux Machine (Any distro tbh as long you know how to set it up) or Raspberry Pi.
- **Printer:** ESC/POS Thermal Printer (Optimized for **Xprinter XP-58IIH** 58mm).
- **Connection:** USB.

## Installation

### 1. System Dependencies (Arch Linux)
Doesn't really have one, it just works and I don't know why


### 2. Python Environment
- mkdir hardcopy && cd hardcopy
- python -m venv venv
- source venv/bin/activate

Install dependencies
- pip install todoist-api-python python-escpos[usb] fastapi[all] python-dotenv todoist-api-python


### 3. Configuration
Edit the `.env` variables in the scripts with your credentials
- **Todoist API Token:** Settings > Integrations > Developer
- **Printer IDs:** Run `lsusb` to find your Vendor/Product hex codes
- **Ngrok Static Domain:** You need to get a static domain from [ngrok](https://ngrok.com). Create an account and get the static domain

## Usage
- **Printing Current Tasks:** `python print_todos.py`
- **Running the Rewards Server:** `python -m uvicorn rewards_server:app --host 127.0.0.1 --port 8000`
- **Running ngrok tunnel (this is for receiving updates from todoist using a webhook):** `ngrok http --domain [STATIC DOMAIN] 8000`


## TODO
- Create a shell script to automate making a systemd service (linux only) so that:
    - It will print the current tasks at exactly 10am
    - Automate running the webhook server as well as the ngrok without manually doing anything
    - Registering a service so that every 8pm Sunday it will print a summary of what you did for the entire week (any many more actually)

