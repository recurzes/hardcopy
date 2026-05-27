# HARDCOPY
**Physicalizing Productivity for the Dopamine-Starved Brain.**

Hardcopy turns your abstract Todoist list into a physical reality. Inspired by the work of [Coding with Lewis](https://www.youtube.com/@CodingWithLewis), this project utilizes a thermal receipt printer to create daily "contracts" and real-time "reward slips" to gamify the workflow of software developers and power users.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg) ![Arch Linux](https://img.shields.io/badge/OS-Arch%20Linux-1793d1.svg) ![Hardware](https://img.shields.io/badge/Hardware-Thermal%20Printer-black.svg)

## System Architecture

The system operates on four distinct modules:

1. **The Contract (Morning):** Fetches "Today's" tasks and prints a physical checklist to sign.
2. **The Daemon (All Day):** A local FastAPI server listening to Todoist Webhooks. When a task is checked off digitally, the printer immediately prints a randomized "XP Reward" slip.
3. **The Boss Fight (Weekly):** A Sunday night summary that calculates total XP, determines if you "defeated" the week, and prints a rank (S+ to F).
4. **Brain Dump (On Demand):** Describe vague intentions in plain text; an LLM breaks them into concrete Todoist tasks with due dates and priorities, then optionally prints a "Quest Briefing" receipt.

## Project Structure

```
hardcopy/
├── src/
│   ├── config.py          # env vars and constants
│   ├── llm.py             # LLM provider abstraction
│   ├── printer.py         # USB printer helpers
│   ├── server.py          # FastAPI webhook app
│   └── commands/
│       ├── todos.py       # daily task contract
│       ├── dump.py        # brain dump → Todoist tasks
│       ├── add.py         # quick task capture
│       ├── habits.py      # habit checklist
│       ├── reward.py      # reward slip printing
│       ├── boss.py        # weekly raid report
│       └── barcodes.py    # barcode utility
├── systemd/               # user systemd unit templates
├── scripts/               # install helpers
├── scratch/               # experiments
└── tasks/                 # branchable task specs
```

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

Install dependencies:
- pip install -r requirements.txt

### 3. Configuration
Copy `.env.example` to `.env` and fill in your credentials:
- **Todoist API Token:** Settings > Integrations > Developer
- **Printer IDs:** Run `lsusb` to find your Vendor/Product hex codes (defaults in `src/config.py`)
- **Ngrok Static Domain:** You need to get a static domain from [ngrok](https://ngrok.com). Create an account and get the static domain
- **LLM Provider (brain dump):** Set `LLM_PROVIDER` to `openai`, `anthropic`, or `ollama`
- **LLM API Key:** Required for OpenAI and Anthropic; optional for local Ollama
- **LLM Model:** Optional override (defaults: `gpt-4o-mini`, `claude-sonnet-4-20250514`, `llama3.2`)

## Usage

Root scripts delegate to `src/commands/`:

- **Printing Current Tasks:** `python -m src.commands.todos`
- **Printing Habits:** `python -m src.commands.habits`
- **Weekly Boss Report:** `python -m src.commands.boss`
- **Running the Rewards Server:** `python -m uvicorn src.server:app --host 127.0.0.1 --port 8000`
- **Running ngrok tunnel (for Todoist webhooks):** `ngrok http --domain [STATIC DOMAIN] 8000`

### Brain Dump

Turn a vague description into organized Todoist tasks via LLM:

```bash
# One-liner
python -m src.commands.dump "prep for friday presentation and clean my room"

# Interactive (multi-line input, blank line to finish)
python -m src.commands.dump

# Skip confirmation prompts
python -m src.commands.dump "buy groceries and call dentist" -y
```

Flow: LLM decomposes your text → preview → confirm (`Y`/`n`, or `e` to edit) → tasks created in Todoist → optional "Quest Briefing" receipt print.

Requires `LLM_PROVIDER` and `LLM_API_KEY` (for OpenAI/Anthropic) in `.env`. For local models, use `LLM_PROVIDER=ollama` and optionally set `OLLAMA_HOST`.

### Quick Capture

Add tasks to Todoist with minimal friction:

```bash
# Just the task
python -m src.commands.add "buy groceries"

# Natural language date
python -m src.commands.add "call dentist tomorrow"

# Priority (!1 = urgent, !4 = low)
python -m src.commands.add "submit report by friday !1"

# Multiple tasks (semicolon-separated)
python -m src.commands.add "laundry today; groceries tomorrow; clean kitchen friday"

# Interactive prompt
python -m src.commands.add
```

Dates are passed to Todoist's natural-language parser — no extra dependencies.

## Scheduled Automation

Install user systemd units (no root required for the services themselves):

```bash
chmod +x scripts/install-services.sh
./scripts/install-services.sh
```

Optional ngrok tunnel service (requires `NGROK_DOMAIN` in `.env`):

```bash
./scripts/install-services.sh --with-ngrok
```

This enables:
- **10:00 daily** — print today's Todoist tasks
- **Sunday 20:00** — weekly boss report
- **Always on** — webhook reward server on `127.0.0.1:8000`

Check status:

```bash
systemctl --user list-timers 'hardcopy-*'
systemctl --user status hardcopy-rewards.service
journalctl --user -u hardcopy-todos.service
```

Manual trigger:

```bash
systemctl --user start hardcopy-todos.service
systemctl --user start hardcopy-boss.service
```

Timers run while logged out after enabling linger:

```bash
loginctl enable-linger "$USER"
```

Printer USB access for systemd user services:

```bash
sudo usermod -aG lp "$USER"
# re-login required
```

