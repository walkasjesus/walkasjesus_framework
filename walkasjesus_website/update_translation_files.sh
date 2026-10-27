#!/bin/bash
# Refresh and translate the requested locales (default: all non-English site languages).
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

"$python" - "$@" <<'PY' 2>&1 | tee -a "$log"
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'walkasjesus_website.settings')
import django
import polib
django.setup()

from django.conf import settings
from django.core.management import call_command, CommandError
from django.core.management.commands.makemessages import Command

supported = {code for code, _ in settings.LANGUAGES if code != 'en'}
locales = sys.argv[1:] or sorted(supported)
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
    call_command('auto_translate', locales=[locale])
    call_command('compilemessages', locale=[locale], ignore_patterns=['venv/*', '.venv/*', 'data/*'])
PY
