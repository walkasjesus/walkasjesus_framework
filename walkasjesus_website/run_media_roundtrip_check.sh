#!/usr/bin/env bash
set -euo pipefail

# Verifies media.csv roundtrip stability against shared media table.
# Workflow:
# 1) optional clean shared media rows
# 2) import media.csv
# 3) export media.csv
# 4) import media.csv again
# 5) assert stable counts and zero duplicate csv rows

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-../.venv/bin/python}"
CLEAN_FIRST="true"

if [[ "${1:-}" == "--no-clean" ]]; then
  CLEAN_FIRST="false"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found or not executable: $PYTHON_BIN"
  echo "Hint: set PYTHON_BIN env var, for example: PYTHON_BIN=../.venv/bin/python"
  exit 1
fi

echo "Running media roundtrip check"
echo "Root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
echo "Clean first: $CLEAN_FIRST"

if [[ "$CLEAN_FIRST" == "true" ]]; then
  "$PYTHON_BIN" manage.py shell -c "from walkasjesus_app.models import LawOfMessiahDrawing; c,_=LawOfMessiahDrawing.objects.all().delete(); print('DELETED_SHARED_MEDIA_ROWS=', c)"
fi

"$PYTHON_BIN" manage.py import_media data/media/media.csv
COUNT_AFTER_IMPORT_1=$("$PYTHON_BIN" manage.py shell -c "from walkasjesus_app.models import LawOfMessiahDrawing; print(LawOfMessiahDrawing.objects.count())" | tail -n 1)

echo "COUNT_AFTER_IMPORT_1=$COUNT_AFTER_IMPORT_1"

"$PYTHON_BIN" manage.py export_media data/media/media.csv

CSV_STATS=$("$PYTHON_BIN" - <<'PY'
import csv
from collections import Counter
from pathlib import Path

p = Path('data/media/media.csv')
with p.open(newline='') as f:
    reader = csv.DictReader(f, delimiter=';')
    rows = list(reader)

required = [
    'step', 'lawofmessiah', 'lesson',
    'media_author', 'media_title', 'media_description_en',
    'media_target_audience', 'media_lang', 'media_type',
    'media_public', 'media_img_url', 'media_url'
]

missing = [c for c in required if c not in (reader.fieldnames or [])]

keys = [(
    (r.get('step') or '').strip(),
    (r.get('lawofmessiah') or '').strip(),
    (r.get('lesson') or '').strip(),
    (r.get('media_author') or '').strip(),
    (r.get('media_title') or '').strip(),
    (r.get('media_description_en') or '').strip(),
    (r.get('media_target_audience') or '').strip(),
    (r.get('media_lang') or '').strip(),
    (r.get('media_type') or '').strip().lower(),
    (r.get('media_public') or '').strip().lower(),
    (r.get('media_img_url') or '').strip(),
    (r.get('media_url') or '').strip(),
) for r in rows]

dupes = sum(c - 1 for c in Counter(keys).values() if c > 1)

print(f'CSV_ROWS={len(rows)}')
print(f'CSV_DUPLICATE_ROWS={dupes}')
print(f'CSV_MISSING_COLUMNS={"|".join(missing)}')
PY
)

echo "$CSV_STATS"

"$PYTHON_BIN" manage.py import_media data/media/media.csv
COUNT_AFTER_IMPORT_2=$("$PYTHON_BIN" manage.py shell -c "from walkasjesus_app.models import LawOfMessiahDrawing; print(LawOfMessiahDrawing.objects.count())" | tail -n 1)

echo "COUNT_AFTER_IMPORT_2=$COUNT_AFTER_IMPORT_2"

CSV_DUPLICATE_ROWS=$(echo "$CSV_STATS" | awk -F= '/^CSV_DUPLICATE_ROWS=/{print $2}')
CSV_MISSING_COLUMNS=$(echo "$CSV_STATS" | awk -F= '/^CSV_MISSING_COLUMNS=/{print $2}')

if [[ "$CSV_DUPLICATE_ROWS" != "0" ]]; then
  echo "FAIL: Duplicate rows found in media.csv: $CSV_DUPLICATE_ROWS"
  exit 1
fi

if [[ -n "$CSV_MISSING_COLUMNS" ]]; then
  echo "FAIL: Missing required columns in media.csv: $CSV_MISSING_COLUMNS"
  exit 1
fi

if [[ "$COUNT_AFTER_IMPORT_1" != "$COUNT_AFTER_IMPORT_2" ]]; then
  echo "FAIL: Roundtrip is not stable: count changed from $COUNT_AFTER_IMPORT_1 to $COUNT_AFTER_IMPORT_2"
  exit 1
fi

echo "PASS: media.csv roundtrip is stable"
echo "Stable shared media count: $COUNT_AFTER_IMPORT_2"
