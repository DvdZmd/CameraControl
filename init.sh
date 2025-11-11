#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Only activate the venv if not already inside one
if [ -z "$VIRTUAL_ENV" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment already active: $VIRTUAL_ENV"
fi

python3 ./app.py