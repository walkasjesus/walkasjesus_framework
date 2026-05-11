#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [[ -x "$SCRIPT_DIR/../venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/../venv/bin/python"
else
	PYTHON_BIN="python3"
fi

"$PYTHON_BIN" manage.py shell -c "from django.core.cache import cache; cache.clear()"
