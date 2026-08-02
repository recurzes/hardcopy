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
│       ├── plan.py        # evening auto-planner
│       ├── split.py       # split big tasks into subtasks
│       ├── focus.py       # pomodoro focus sessions
│       ├── habits.py      # habit checklist
│       ├── reward.py      # reward slip printing
│       ├── boss.py        # weekly raid report
│       ├── freegames.py   # free games loot drop receipt
│       ├── quiz_ingest.py # study note ingestion + Q&A pre-generation
│       ├── quiz.py        # quiz daemon (scheduled Q&A printing)
│       ├── quiz_answer.py # manual answer trigger
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
- **Free Games Loot Drop:** `python -m src.commands.freegames`
- **Quiz Daemon:** `python -m src.commands.quiz`
- **Manual Answer Trigger:** `python -m src.commands.quiz_answer`
- **Running the Rewards Server:** `python -m uvicorn src.server:app --host 127.0.0.1 --port 8000`
- **Running ngrok tunnel (for Todoist webhooks):** `ngrok http --domain [STATIC DOMAIN] 8000`

### Quiz Daemon

RAG-powered study quiz system that prints question and answer receipts on a schedule.

**Step 1 — Ingest your notes (run once per document set):**
```bash
# Feed your study notes — generates >=50 Q&A pairs automatically
python -m src.commands.quiz_ingest /path/to/re_notes.pdf /path/to/game_hacking.txt

# Clear and re-ingest
python -m src.commands.quiz_ingest notes.pdf --reset

# Check what's ingested and how many questions are in the pool
python -m src.commands.quiz_ingest --list

# Re-generate questions without re-ingesting (e.g. after switching LLM)
python -m src.commands.quiz_ingest --regen-pool
```

**Step 2 — Run the quiz daemon:**
```bash
# Start the background daemon (default: quiz every 2 hours, answer after 5 min)
python -m src.commands.quiz

# Customize intervals
python -m src.commands.quiz --interval 60 --answer-delay 10

# One-shot quiz right now (for testing)
python -m src.commands.quiz --once

# No 30-min warning slip
python -m src.commands.quiz --no-warning
```

**Manual answer trigger (any time before the scheduled answer):**
```bash
# Print the answer right now — daemon will skip its own answer slip
python -m src.commands.quiz_answer

# Review a specific past quiz answer
python -m src.commands.quiz_answer --id 7

# List recent quiz history in the terminal
python -m src.commands.quiz_answer --history
```

The quiz pipeline: notes → chunk → embed (local `sentence-transformers`) → store in SQLite → LLM generates ≥50 Q&A pairs upfront → daemon pops from pool every interval. Configure via `.env`:
```dotenv
QUIZ_INTERVAL=120        # minutes between quizzes
QUIZ_ANSWER_DELAY=5      # minutes before answer slip prints
QUIZ_TOPIC=Reverse Engineering and Game Hacking
QUIZ_POOL_MIN=50         # minimum questions generated on ingest
```

Requires `LLM_PROVIDER` and `LLM_API_KEY` (or Ollama) in `.env` for question generation.

### Free Games Loot Drop

Print a receipt of all currently free game giveaways across platforms, each with a scannable QR code to claim it:

```bash
# Print all free games across all platforms
python -m src.commands.freegames

# Filter to a specific platform
python -m src.commands.freegames --platform steam
python -m src.commands.freegames --platform epic-games-store
python -m src.commands.freegames --platform ps5

# Limit to the first N games
python -m src.commands.freegames --max 5

# Text-only (no QR codes, faster print)
python -m src.commands.freegames --no-qr
```

Powered by the [GamerPower API](https://www.gamerpower.com/api) — no API key required. Fetches active game giveaways from Steam, Epic Games, GOG, PlayStation, Xbox, Nintendo Switch, itch.io, and more. Each game entry shows its title, expiry date (or "Permanent"), and a QR code linking directly to its claim page.

**Supported `--platform` slugs:** `steam`, `epic-games-store`, `gog`, `ps4`, `ps5`, `xbox-one`, `xbox-series-xs`, `switch`, `android`, `ios`, `itch.io`, `drm-free`, `pc`

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

### Evening Planner

LLM drafts tomorrow's plan from your Todoist backlog:

```bash
# Interactive — preview, confirm, optionally apply
python -m src.commands.plan

# Non-interactive (systemd) — apply + print receipt
python -m src.commands.plan --auto
```

Flow: analyzes overdue/upcoming/unscheduled tasks → LLM suggests 3–8 tasks sized to your recent completion rate → confirm (`Y`/`n`/`e`) → optionally reschedules to tomorrow → prints "Tomorrow's Battle Plan" receipt.

Requires `LLM_PROVIDER` and `LLM_API_KEY` in `.env`.

### Task Splitter

Break overwhelming Todoist tasks into 15–30 minute micro-quests:

```bash
# Scan for splittable tasks (interactive Y/n/s per task)
python -m src.commands.split

# Split all candidates without prompting
python -m src.commands.split -y
```

Flow: scans for large/vague tasks → LLM proposes 3–7 subtasks → confirm → creates Todoist subtasks → prints "Quest Breakdown" receipt.

When the webhook server is running, newly added tasks that look too big trigger a "Quest Too Big To Solo" suggestion receipt (subscribe to `item:added` in Todoist webhooks).

Requires `LLM_PROVIDER` and `LLM_API_KEY` in `.env`.

### Focus Session

Pomodoro-style focus with printed start/end/checkpoint receipts:

```bash
# 25-minute session (default)
python -m src.commands.focus "work on presentation slides"

# Custom duration (45 min with mid-session check-in)
python -m src.commands.focus "research paper outline" 45

# Complete matching Todoist task when session finishes
python -m src.commands.focus "draft meeting agenda" 25 --complete

# Disable checkpoint receipt for long sessions
python -m src.commands.focus "deep work block" 60 --no-checkin
```

Prints session start receipt, terminal countdown, optional halfway checkpoint (>30 min), completion reward with XP/streak, or partial credit on early exit (Ctrl+C after 1+ min). Streak data stored in `~/.local/share/hardcopy/focus_streaks.json`.

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
- **21:00 daily** — evening auto-planner (draft + apply tomorrow's plan)
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
systemctl --user start hardcopy-planner.service
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

