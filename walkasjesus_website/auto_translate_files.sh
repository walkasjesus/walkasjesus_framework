#!/bin/bash
# Translate existing catalogs for the requested locales, then compile them.
set -euo pipefail
cd "$(dirname "$0")"

if [[ -n "${WAJ_TRANSLATION_PYTHON:-}" ]]; then
    python="$WAJ_TRANSLATION_PYTHON"
elif [[ -x ./venv/bin/python ]]; then
    python=./venv/bin/python
elif [[ -x ../venv/bin/python ]]; then
    python=../venv/bin/python
else
    python=python3
fi

mkdir -p log
log="log/translation.$(date +%Y%m%d).log"
args=()
compile_args=()
dry_run=false
while (($#)); do
    case "$1" in
        --scope|--limit|--request-interval|--provider|--model-path)
            if (($# < 2)); then
                echo "Missing value for $1" >&2
                exit 2
            fi
            args+=("$1" "$2")
            shift 2
            ;;
        --dry-run)
            args+=("$1")
            dry_run=true
            shift
            ;;
        --*)
            echo "Unknown option: $1" >&2
            exit 2
            ;;
        *)
            args+=(--locale "$1")
            compile_args+=(--locale "$1")
            shift
            ;;
    esac
done

status=0
"$python" manage.py auto_translate "${args[@]}" 2>&1 | tee -a "$log" || status=$?
if ! "$dry_run"; then
    "$python" -m django compilemessages "${compile_args[@]}" --ignore='venv/*' --ignore='.venv/*' --ignore='data/*' 2>&1 | tee -a "$log"
fi
exit "$status"
