#!/bin/bash
# Translate existing catalogs for the requested locales, then compile them.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x ./venv/bin/python ]]; then
    python=./venv/bin/python
elif [[ -x ../venv/bin/python ]]; then
    python=../venv/bin/python
else
    python=python3
fi

mkdir -p log
log="log/translation.$(date +%Y%m%d).log"
args=()
for locale in "$@"; do
    args+=(--locale "$locale")
done

"$python" manage.py auto_translate "${args[@]}" 2>&1 | tee -a "$log"
"$python" -m django compilemessages "${args[@]}" --ignore='venv/*' --ignore='.venv/*' --ignore='data/*' 2>&1 | tee -a "$log"
