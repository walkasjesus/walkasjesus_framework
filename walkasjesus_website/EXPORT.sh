#!/usr/bin/env bash
#
# Export current database content to local CSV files only.
# No remote actions are performed (no push, no PR, no remote rewrites).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

TODAY="$(date +%Y%m%d)"
START="$(date '+%Y-%m-%d %H:%M:%S')"
LOG="log/commandments.${TODAY}.log"
BRANCH_STAMP="$(date +%Y%m%d_%H%M%S)"

if [[ -f ./venv/Scripts/activate ]]; then
    # Windows virtualenv (Git Bash)
    source ./venv/Scripts/activate
    PYTHON_BIN="python"
elif [[ -f ./venv/bin/activate ]]; then
    source ./venv/bin/activate
    PYTHON_BIN="python3"
elif [[ -x ../.venv/bin/python ]]; then
    PYTHON_BIN="../.venv/bin/python"
else
    PYTHON_BIN="python3"
fi

ensure_branch_for_submodule() {
    local submodule_path="$1"
    local branch_suffix="$2"
    local created="false"

    if [[ ! -d "$submodule_path/.git" && ! -f "$submodule_path/.git" ]]; then
        echo "WARN: ${submodule_path} is not a git repository. Skipping branch check."
        return 0
    fi

    local current_branch
    current_branch="$(git -C "$submodule_path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

    if [[ -z "$current_branch" ]]; then
        echo "WARN: Unable to detect branch for ${submodule_path}."
        return 0
    fi

    if [[ "$current_branch" == "HEAD" || "$current_branch" == "master" || "$current_branch" == "main" ]]; then
        local new_branch="export_${branch_suffix}_${BRANCH_STAMP}"
        if git -C "$submodule_path" show-ref --verify --quiet "refs/heads/${new_branch}"; then
            git -C "$submodule_path" checkout "$new_branch" >/dev/null
        else
            git -C "$submodule_path" checkout -b "$new_branch" >/dev/null
            created="true"
        fi
        if [[ "$created" == "true" ]]; then
            echo "INFO: ${submodule_path} switched from ${current_branch} to ${new_branch} (created)"
        else
            echo "INFO: ${submodule_path} switched from ${current_branch} to ${new_branch}"
        fi
    else
        echo "INFO: ${submodule_path} keeping existing branch ${current_branch}"
    fi
}

report_csv_change() {
    local repo_path="$1"
    local file_path="$2"
    local label="$3"

    if git -C "$repo_path" diff --quiet -- "$file_path"; then
        echo "INFO: ${label} unchanged"
    else
        echo "INFO: ${label} changed"
        git -C "$repo_path" status --short -- "$file_path"
    fi
}

echo "INFO: ${START} - Preparing export branches" | tee -a "$LOG"
ensure_branch_for_submodule "data/biblereferences" "biblereferences" | tee -a "$LOG"
ensure_branch_for_submodule "data/media" "media" | tee -a "$LOG"

echo "INFO: ${START} - Start exporting Commandments" | tee -a "$LOG"
"$PYTHON_BIN" manage.py export_commandments data/biblereferences/commandments.csv | tee -a "$LOG"
END="$(date '+%Y-%m-%d %H:%M:%S')"
echo "INFO: ${END} - Ended exporting Commandments" | tee -a "$LOG"

echo "INFO: ${END} - Start exporting Media Resources" | tee -a "$LOG"
"$PYTHON_BIN" manage.py export_media data/media/media.csv | tee -a "$LOG"
END="$(date '+%Y-%m-%d %H:%M:%S')"
echo "INFO: ${END} - Ended exporting Media Resources" | tee -a "$LOG"

echo "INFO: ${END} - Export result summary" | tee -a "$LOG"
report_csv_change "data/biblereferences" "commandments.csv" "biblereferences/commandments.csv" | tee -a "$LOG"
report_csv_change "data/media" "media.csv" "media/media.csv" | tee -a "$LOG"

echo "INFO: Finished local export only. No push was performed." | tee -a "$LOG"
