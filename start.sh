#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/Save-Restricted-Content-Safe-Bot-main/Save-Restricted-Content-Safe-Bot-main"
export PORT="${PORT:-8080}"

python -m safe_repo &
bot_pid=$!

cleanup() {
	kill "$bot_pid" "$web_pid" 2>/dev/null || true
	wait "$bot_pid" "$web_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 0 railway_server:app &
web_pid=$!
wait -n "$bot_pid" "$web_pid"
