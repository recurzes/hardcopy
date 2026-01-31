# HARDCOPY
**Physicalizing Productivity for the Dopamine-Starved Brain.**

Hardcopy turns your abstract Todoist list into a physical reality. Inspired by the work of [CodingLewis](https://www.youtube.com/@CodingLewis), this project utilizes a thermal receipt printer to create daily "contracts" and real-time "reward slips" to gamify the workflow of software developers and power users.

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


## Usage
No manual for the usage as of the moment (will update it later)

