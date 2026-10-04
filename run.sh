#!/usr/bin/env bash
# Spherix Clinic Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python app.py "$@"
elif command -v python3 &>/dev/null; then
    python3 app.py "$@"
else
    python app.py "$@"
fi
