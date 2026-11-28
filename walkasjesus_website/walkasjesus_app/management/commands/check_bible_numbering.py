import json
import math
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from walkasjesus_app.lib.bible_numbering_checks import _BOOK_CODES, scan_numbering_cache
from walkasjesus_app.lib.bible_numbering_fetch import NumberingSourceFetcher
from walkasjesus_app.models import BibleTranslation
from walkasjesus_app.models.bible_numbering import BibleNumberingReview


class Command(BaseCommand):
    help = 'Check cached numbering; fetch missing provider passages within a strict request budget.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--cache-path', type=Path, default=Path(settings.BASE_DIR) / 'bible_api_cache.json')
        parser.add_argument('--bible-ids', nargs='+', help='Only check these translation IDs.')
        parser.add_argument('--language', help='Filter translation language, e.g. nl or en (cached catalogue only).')
        parser.add_argument('--books', nargs='+', default=['Joel', 'Hosea', 'Psalms'],
                            help='Book names (case-insensitive, e.g. numbers) or all for every book.')
        parser.add_argument('--max-requests', type=int, default=100, help='Maximum API calls, including metadata and failures.')
        parser.add_argument('--cache-only', action='store_true', help='Do not acquire missing source data (zero API calls).')
        parser.add_argument('--sleep', type=float, default=0.5, help='Seconds between API requests.')
        parser.add_argument('--output', type=Path, help='Also write a text-free JSON report to this file.')
        parser.add_argument('--no-save', action='store_true', help='Do not update the admin dossiers.')
        parser.add_argument('--fail-on-findings', action='store_true', help='Exit nonzero if structural findings exist.')

    def handle(self, *args, **options):
        book_names = {name.lower(): name for name in _BOOK_CODES}
        books = []
        for value in options['books']:
            name = value.strip().lower()
            if name == 'all':
                books.append('all')
            elif name in book_names:
                books.append(book_names[name])
            else:
                raise CommandError(f'Unknown Bible book: {value!r}. Use a canonical book name or all.')
        books = list(_BOOK_CODES) if 'all' in books else list(dict.fromkeys(books))
        if not 0 <= options['max_requests'] <= 100 or not math.isfinite(options['sleep']) or options['sleep'] < 0:
            raise CommandError('Request budget must be 0–100 and sleep must be finite and nonnegative.')
        if options['output'] and options['output'].resolve() == options['cache_path'].resolve():
            raise CommandError('The report output must not overwrite the source cache.')
        ids = options['bible_ids']
        if ids and any(not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', bible_id) for bible_id in ids):
            raise CommandError('Invalid translation ID.')
        bibles = BibleTranslation().all()
        bible_names = {bible.id: bible.name for bible in bibles}
        language = (options['language'] or '').strip().lower()
        if options['language'] is not None and not language:
            raise CommandError('Language must not be empty.')
        language_ids = {
            bible.id for bible in bibles
            if str(getattr(bible, 'language', '') or '').strip().lower() == language
        } if language else None
        if language and not language_ids:
            raise CommandError(f'Language {language!r} is not available in the cached Bible catalogue.')
        scan_ids = set(ids) if ids else None
        try:
            report = scan_numbering_cache(
                options['cache_path'], scan_ids,
                max_ttl_seconds=int(settings.BIBLE_API_CACHE_TIMEOUT_SECONDS), books=books)
        except (OSError, ValueError) as error:
            raise CommandError(f'Cannot check the API.Bible cache: {error}') from error
        if language_ids is not None:
            report['bibles'] = [result for result in report['bibles'] if result['bible_id'] in language_ids]
            scan_ids = {result['bible_id'] for result in report['bibles']}
        acquisition = {'requests': 0, 'budget_exhausted': False, 'errors': [], 'skipped': []}
        if not options['cache_only'] and options['max_requests'] and report['bibles']:
            selected = list(dict.fromkeys(ids or [result['bible_id'] for result in report['bibles']]))
            if language_ids is not None:
                selected = [bible_id for bible_id in selected if bible_id in language_ids]
            fetcher = NumberingSourceFetcher(
                options['cache_path'], settings.BIBLE_API_KEY, options['max_requests'], options['sleep'],
                int(settings.BIBLE_API_CACHE_TIMEOUT_SECONDS))
            try:
                acquisition = fetcher.acquire(selected, books)
            except (OSError, ValueError) as error:
                raise CommandError(f'Cannot acquire source data: {error}') from error
            finally:
                fetcher.close()
            report = scan_numbering_cache(
                options['cache_path'], scan_ids,
                max_ttl_seconds=int(settings.BIBLE_API_CACHE_TIMEOUT_SECONDS), books=books)
        report['api_requests'] = acquisition['requests']
        report['acquisition'] = acquisition
        report['generated_at'] = timezone.now().isoformat()
        if options['output']:
            try:
                options['output'].write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            except OSError as error:
                raise CommandError(f'Cannot write the report: {error}') from error
        if not options['no_save']:
            with transaction.atomic():
                for result in report['bibles']:
                    review, _created = BibleNumberingReview.objects.get_or_create(bible_id=result['bible_id'])
                    review.report = {
                        **result,
                        'acquisition': acquisition,
                    }
                    review.scanned_at = timezone.now()
                    review.mapping_revision = report['mapping_revision']
                    review.save(update_fields=['report', 'scanned_at', 'mapping_revision'])
        if not report['bibles']:
            self.stderr.write(self.style.WARNING('No cached passage entries found; nothing can be verified.'))
        for warning in report['warnings']:
            self.stderr.write(self.style.WARNING(warning))
        for message in acquisition['errors'] + acquisition['skipped']:
            self.stderr.write(self.style.WARNING(message))
        if acquisition['budget_exhausted']:
            self.stdout.write('Request budget reached. Run again to continue using the updated cache.')
        findings = 0
        for result in report['bibles']:
            count = len(result['findings'])
            findings += count
            name = bible_names.get(result['bible_id']) or 'name unavailable in cached catalogue'
            self.stdout.write(
                f"{result['bible_id']} ({name}): fresh={result['entries'].get('fresh', 0)} "
                f"expired={result['entries'].get('expired', 0)} "
                f"unknown_expiry={result['entries'].get('unknown_expiry', 0)} "
                f"untrusted_ttl={result['entries'].get('untrusted_ttl', 0)} "
                f"chapters={result['cached_chapters']} findings={count}"
            )
            for book in books:
                scope = book.lower()
                coverage = result['scopes'][scope]
                self.stdout.write(
                    f"  {scope}: {coverage['state']} "
                    f"({coverage['cached_candidates']}/{coverage['expected_cases']} cached candidates)"
                )
        self.stdout.write(
            f"API requests: {acquisition['requests']}/{options['max_requests']}. "
            'Source acquisition does not automatically approve production mappings.')
        if acquisition['errors']:
            raise CommandError('Source acquisition was incomplete; errors are listed above and in the report.')
        if options['fail_on_findings'] and findings:
            raise CommandError(f'{findings} structural findings require review.')
