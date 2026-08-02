#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_USER_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
WITH_NGROK=0

usage() {
    cat <<EOF
Usage: $(basename "$0") [--with-ngrok]

Install Hardcopy user systemd units and enable timers/services.

Options:
  --with-ngrok   Also install and enable hardcopy-ngrok.service
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-ngrok)
            WITH_NGROK=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif [[ -x "$REPO_ROOT/venv/bin/python" ]]; then
    PYTHON="$REPO_ROOT/venv/bin/python"
else
    echo "No virtualenv found at $REPO_ROOT/.venv or $REPO_ROOT/venv" >&2
    exit 1
fi

if [[ ! -f "$REPO_ROOT/.env" ]]; then
    echo "Warning: $REPO_ROOT/.env not found. Create it from .env.example before running jobs." >&2
fi

NGROK_BIN="$(command -v ngrok || true)"
if [[ $WITH_NGROK -eq 1 && -z "$NGROK_BIN" ]]; then
    echo "ngrok not found in PATH. Install ngrok or omit --with-ngrok." >&2
    exit 1
fi

mkdir -p "$SYSTEMD_USER_DIR"

install_unit() {
    local unit="$1"
    sed \
        -e "s|@HARDCOPY_ROOT@|$REPO_ROOT|g" \
        -e "s|@HARDCOPY_PYTHON@|$PYTHON|g" \
        -e "s|@NGROK_BIN@|${NGROK_BIN:-/usr/bin/ngrok}|g" \
        "$REPO_ROOT/systemd/$unit" > "$SYSTEMD_USER_DIR/$unit"
}

UNITS=(
    hardcopy-todos.service
    hardcopy-todos.timer
    hardcopy-rewards.service
    hardcopy-boss.service
    hardcopy-boss.timer
    hardcopy-planner.service
    hardcopy-planner.timer
    hardcopy-quiz.service
)

if [[ $WITH_NGROK -eq 1 ]]; then
    UNITS+=(hardcopy-ngrok.service)
fi

for unit in "${UNITS[@]}"; do
    install_unit "$unit"
    echo "Installed $unit"
done

systemctl --user daemon-reload

systemctl --user enable --now hardcopy-todos.timer
systemctl --user enable --now hardcopy-boss.timer
systemctl --user enable --now hardcopy-planner.timer
systemctl --user enable --now hardcopy-rewards.service
systemctl --user enable --now hardcopy-quiz.service

if [[ $WITH_NGROK -eq 1 ]]; then
    systemctl --user enable --now hardcopy-ngrok.service
fi

cat <<EOF

Hardcopy systemd units installed.

Status:
  systemctl --user list-timers 'hardcopy-*'
  systemctl --user status hardcopy-rewards.service

Logs:
  journalctl --user -u hardcopy-todos.service
  journalctl --user -u hardcopy-boss.service
  journalctl --user -u hardcopy-planner.service
  journalctl --user -u hardcopy-rewards.service
  journalctl --user -u hardcopy-quiz.service

Manual runs:
  systemctl --user start hardcopy-todos.service
  systemctl --user start hardcopy-boss.service
  systemctl --user start hardcopy-planner.service

Quiz commands:
  # Ingest study notes and pre-generate 50 questions
  python -m src.commands.quiz_ingest /path/to/notes.pdf
  # Manually print the current pending answer
  python -m src.commands.quiz_answer
  # List recent quiz history
  python -m src.commands.quiz_answer --history

Timers also run when logged out after enabling linger:
  loginctl enable-linger "$USER"

Printer USB access (re-login after adding group):
  sudo usermod -aG lp "$USER"
EOF
