#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/Save-Restricted-Content-Safe-Bot-main/Save-Restricted-Content-Safe-Bot-main"
exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 1 --threads 4 --timeout 0 railway_server:app
