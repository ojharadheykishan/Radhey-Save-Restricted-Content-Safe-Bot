#!/usr/bin/env bash
set -euo pipefail

python -m safe_repo &
bot_pid=$!

cleanup() {
    kill "$bot_pid" 2>/dev/null || true
}
trap cleanup EXIT TERM INT

gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 0 railway_server:app &
web_pid=$!
wait "$web_pid"
