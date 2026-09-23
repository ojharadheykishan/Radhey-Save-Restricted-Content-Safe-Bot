#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/Save-Restricted-Content-Safe-Bot-main/Save-Restricted-Content-Safe-Bot-main"
exec python app.py
