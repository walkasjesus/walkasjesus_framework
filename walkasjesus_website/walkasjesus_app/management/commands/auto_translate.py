import os

import math
import polib
import requests
from django.apps import apps
from django.core.management import BaseCommand, CommandError
from translate_tool import PoTranslator
from translate_tool.local_translator import LocalPoTranslator

from walkasjesus_website.settings import BASE_DIR, LANGUAGES, LOCALE_PATHS


def is_content_entry(entry):
    # Database messages historically had no source references. Synced model
    # references keep them identifiable after makemessages has run again.
    return not entry.occurrences or all(
        path.startswith('model:') for path, _ in entry.occurrences
    )


class Command(BaseCommand):
    help = 'Translate missing or fuzzy PO entries, preserving existing translations.'

    def add_arguments(self, parser):
        parser.add_argument('--locale', action='append', dest='locales')
        parser.add_argument('--scope', choices=['all', 'ui', 'content'], default='all')
        parser.add_argument('--limit', type=int, help='Maximum entries across all selected catalogs.')
        parser.add_argument('--request-interval', type=float, default=1.0,
                            help='Minimum seconds between Google requests (default: 1).')
        parser.add_argument('--dry-run', action='store_true', help='Show pending counts without translating.')
        parser.add_argument('--provider', choices=['google', 'local'], default='google')
        parser.add_argument('--model-path', help='Installed Argos model directory (required for local inference).')

    def handle(self, *args, **options):
        supported_languages = [code for code, name in LANGUAGES]
        languages = options.get('locales') or supported_languages
        unsupported = set(languages) - set(supported_languages)
        if unsupported:
            raise CommandError(f'Unsupported locales: {", ".join(sorted(unsupported))}')

        limit = options.get('limit')
        interval = options['request_interval']
        if limit is not None and limit < 1:
            raise CommandError('--limit must be positive.')
        if not math.isfinite(interval) or interval < 0:
            raise CommandError('--request-interval must be a finite, non-negative number.')
        scope = options['scope']
        entry_filter = None
        if scope != 'all':
            entry_filter = lambda entry: is_content_entry(entry) == (scope == 'content')
        if options['provider'] == 'local':
            if not options['model_path']:
                raise CommandError('--model-path is required for --provider local.')
            translator = LocalPoTranslator(options['model_path'])
        else:
            translator = PoTranslator(request_interval=interval)
        remaining = limit

        for language in languages:
            if language != 'en':
                paths = list(self._po_file_paths(language))
                if not paths:
                    raise CommandError(f'No PO files found for {language}; run makemessages first.')
                for file_path in paths:
                    po = polib.pofile(file_path)
                    pending = [entry for entry in po if PoTranslator.needs_translation(entry)]
                    drafts = sum(not entry.obsolete and 'fuzzy' in entry.flags
                                 and 'Machine translation draft:' in entry.tcomment for entry in po)
                    content_count = sum(is_content_entry(entry) for entry in pending)
                    selected = [entry for entry in pending if entry_filter is None or entry_filter(entry)]
                    batch_size = min(len(selected), remaining) if remaining is not None else len(selected)
                    self.stdout.write(
                        f'{language}: pending UI={len(pending) - content_count}, content={content_count}; '
                        f'scope={scope}, batch={batch_size}, drafts awaiting review={drafts} ({file_path})'
                    )
                    if options['dry_run']:
                        if remaining is not None:
                            remaining -= batch_size
                        continue
                    if not batch_size:
                        continue
                    try:
                        completed = translator.translate(
                            file_path, 'en', language, entry_filter=entry_filter, limit=remaining,
                        )
                    except (requests.RequestException, ValueError, RuntimeError, OSError, KeyError) as exc:
                        response = getattr(exc, 'response', None)
                        retry_after = response.headers.get('Retry-After') if response is not None else None
                        message = f'Translation stopped; completed entries were saved. {exc}'
                        if response is not None and response.status_code == 429:
                            message += ' Google rate limit reached; wait before resuming. Do not repeatedly restart.'
                        if retry_after:
                            message += f' Retry-After: {retry_after}.'
                        raise CommandError(message) from exc
                    if remaining is not None:
                        remaining -= completed

    def _po_file_paths(self, language):
        seen = set()
        base_dir = os.path.abspath(BASE_DIR)
        roots = list(LOCALE_PATHS)
        roots.extend(os.path.join(app_config.path, 'locale') for app_config in apps.get_app_configs())

        for root in roots:
            file_path = os.path.join(root, language, 'LC_MESSAGES', 'django.po')
            normalized = os.path.abspath(file_path)
            if not normalized.startswith(base_dir + os.sep):
                continue
            if normalized in seen or not os.path.exists(normalized):
                continue
            seen.add(normalized)
            yield normalized
