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

if command -v tee >/dev/null 2>&1 && command -v date >/dev/null 2>&1; then
	today=$(date +%Y%m%d)
	start=$(date '+%Y-%m-%d %H:%M:%S')
	log="log/install.${today}.log"
	log_cmd=(tee -a "$log")
else
	start=""
	log_cmd=(cat)
fi

echo "INFO: ${start} - Start cleaning thumbnail caches" | "${log_cmd[@]}"
"$PYTHON_BIN" manage.py repair_media_image_paths | "${log_cmd[@]}"
"$PYTHON_BIN" manage.py thumbnail cleanup | "${log_cmd[@]}"

"$PYTHON_BIN" - <<'PY' | "${log_cmd[@]}"
import os
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')

import django
django.setup()

from django.conf import settings
from walkasjesus_app.models.commandment_media import Drawing
from walkasjesus_app.models.lesson_media import LessonDrawing
from walkasjesus_app.models.law_of_messiah_media import LawOfMessiahDrawing

cache_dir = Path(settings.MEDIA_ROOT) / 'cache'
cache_dir.mkdir(parents=True, exist_ok=True)
before = sum(1 for path in cache_dir.rglob('*') if path.is_file())
regenerated = 0
errors = []

for model in (Drawing, LessonDrawing, LawOfMessiahDrawing):
    queryset = model.objects.exclude(img_url__isnull=True).exclude(img_url='')
    for instance in queryset.iterator():
        try:
            instance.thumbnail_url()
            regenerated += 1
        except Exception as exc:
            errors.append(f"{model._meta.label}:{instance.pk}:{exc}")

after = sum(1 for path in cache_dir.rglob('*') if path.is_file())
print(f"Thumbnail regeneration cache dir: {cache_dir}")
print(f"Thumbnail cache file count before: {before}")
print(f"Thumbnail regeneration count: {regenerated}")
print(f"Thumbnail cache file count after: {after}")
if errors:
    print(f"Thumbnail regeneration errors: {len(errors)}")
    for error in errors[:20]:
        print(error)
    raise SystemExit(1)
PY

if command -v date >/dev/null 2>&1; then
	end=$(date '+%Y-%m-%d %H:%M:%S')
	echo "INFO: ${end} - Ended cleaning thumbnail caches" | "${log_cmd[@]}"
else
	echo "INFO: Ended cleaning thumbnail caches" | "${log_cmd[@]}"
fi
