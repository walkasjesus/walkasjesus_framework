#!/bin/bash
set -e

cd "$(dirname "$0")"

if [[ -f ./venv/Scripts/activate ]]; then
    source ./venv/Scripts/activate
elif [[ -f ./venv/bin/activate ]]; then
    source ./venv/bin/activate
else
    echo "ERROR: cannot find environment binary" >&2
    exit 1
fi

export BIBLE_API_OFFLINE=1
python3 manage.py check_bible_numbering "$@"
