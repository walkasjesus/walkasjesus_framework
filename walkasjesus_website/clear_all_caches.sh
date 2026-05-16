#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -x "$SCRIPT_DIR/venv/bin/python3" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
elif [[ -x "$SCRIPT_DIR/venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif [[ -x "$SCRIPT_DIR/../venv/bin/python3" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/../venv/bin/python3"
elif [[ -x "$SCRIPT_DIR/../venv/bin/python" ]]; then
	PYTHON_BIN="$SCRIPT_DIR/../venv/bin/python"
else
	PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - <<'PY'
import os
import shutil
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')

import django
django.setup()

from django.conf import settings
from django.core.cache import cache

configured_cache_dir = Path(getattr(settings, 'MEDIA_ROOT', '.')) / 'cache'
removed_thumbnail_entries = 0
if configured_cache_dir.exists():
    for child in configured_cache_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
            removed_thumbnail_entries += 1
        else:
            child.unlink()
            removed_thumbnail_entries += 1

backend = settings.CACHES['default']['BACKEND']
preserved_markers = ('verse_text:v1:', 'bible_copyright:v1:')
deleted_cache_keys = 0
preserved_cache_keys = 0

if backend == 'django_redis.cache.RedisCache':
    redis_client = cache.client.get_client(write=True)
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, count=500)
        to_delete = []
        for key in keys:
            decoded_key = key.decode() if isinstance(key, (bytes, bytearray)) else str(key)
            if any(marker in decoded_key for marker in preserved_markers):
                preserved_cache_keys += 1
            else:
                to_delete.append(key)
        if to_delete:
            deleted_cache_keys += redis_client.delete(*to_delete)
        if cursor == 0:
            break
else:
    cache.clear()

print(f"Thumbnail cache dir checked: {configured_cache_dir}")
print(f"Removed thumbnail cache entries: {removed_thumbnail_entries}")
print(f"Deleted non-bible cache keys: {deleted_cache_keys}")
print(f"Preserved bible cache keys: {preserved_cache_keys}")
print(f"Cache backend: {backend}")
PY

bash clean_thumbnail_cache.sh