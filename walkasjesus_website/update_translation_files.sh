#!/bin/bash
# Refresh and translate the requested locales (default: all non-English site languages).
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

"$python" - "$@" <<'PY' 2>&1 | tee -a "$log"
import os
import sys
import argparse

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')
import django
import polib
django.setup()

from django.conf import settings
from django.core.management import call_command, CommandError
from django.core.management.commands.makemessages import Command

supported = {code for code, _ in settings.LANGUAGES if code != 'en'}
parser = argparse.ArgumentParser()
parser.add_argument('locales', nargs='*')
parser.add_argument('--scope', choices=['all', 'ui', 'content'], default='all')
parser.add_argument('--limit', type=int)
parser.add_argument('--request-interval', type=float, default=1.0)
parser.add_argument('--dry-run', action='store_true')
parser.add_argument('--provider', choices=['google', 'local'], default='google')
parser.add_argument('--model-path')
options = parser.parse_args()
locales = options.locales or sorted(supported)
if set(locales) - supported:
    raise CommandError(f'Expected locales from: {", ".join(sorted(supported))}')

for locale in locales:
    # Use Django's extractor; database-backed fields are synced separately below.
    call_command(
        Command(), locale=[locale], extensions=['html', 'py'],
        ignore_patterns=['venv/*', '.venv/*', 'data/*', 'static/*'],
    )
    po_path = os.path.join(settings.LOCALE_PATHS[0], locale, 'LC_MESSAGES', 'django.po')
    po = polib.pofile(po_path)
    po.metadata['Language'] = locale
    po.save()
    call_command('sync_model_translations', locales=[locale])
try:
    call_command(
        'auto_translate', locales=locales, scope=options.scope, limit=options.limit,
        request_interval=options.request_interval, dry_run=options.dry_run,
        provider=options.provider, model_path=options.model_path,
    )
finally:
    if not options.dry_run:
        call_command('compilemessages', locale=locales, ignore_patterns=['venv/*', '.venv/*', 'data/*'])
PY
