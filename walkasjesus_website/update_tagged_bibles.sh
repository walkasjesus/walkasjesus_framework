#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "$0")" && pwd)
repo_root=$(cd "$script_dir/.." && pwd)
submodule_path="walkasjesus_website/data/tagged_bibles"

cd "$repo_root"
git submodule update --init --recursive "$submodule_path"

echo "Tagged Bible data revision:"
git -C "$submodule_path" log -1 --format='%h %cs %s'
