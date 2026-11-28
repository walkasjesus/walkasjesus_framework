import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from walkasjesus_app.lib.bible_numbering_checks import scan_numbering_cache
from walkasjesus_app.models.bible_numbering import BibleNumberingReview, ensure_numbering_checklist


class Command(BaseCommand):
    help = 'Check fresh cached Bible passages without API requests; store review reports, never approvals.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--cache-path', type=Path, default=Path(settings.BASE_DIR) / 'bible_api_cache.json')
        parser.add_argument('--bible-ids', nargs='+', help='Only check these translation IDs.')
        parser.add_argument('--output', type=Path, help='Also write a text-free JSON report to this file.')
        parser.add_argument('--no-save', action='store_true', help='Do not update the admin dossiers.')
        parser.add_argument('--fail-on-findings', action='store_true', help='Exit nonzero if structural findings exist.')

    def handle(self, *args, **options):
        if options['output'] and options['output'].resolve() == options['cache_path'].resolve():
            raise CommandError('The report output must not overwrite the source cache.')
        ids = options['bible_ids']
        if ids and any(not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', bible_id) for bible_id in ids):
            raise CommandError('Invalid translation ID.')
        try:
            report = scan_numbering_cache(
                options['cache_path'], set(ids) if ids else None,
                max_ttl_seconds=int(settings.BIBLE_API_CACHE_TIMEOUT_SECONDS))
        except (OSError, ValueError) as error:
            raise CommandError(f'Cannot check the API.Bible cache: {error}') from error
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
                    review.report = result
                    review.scanned_at = timezone.now()
                    review.mapping_revision = report['mapping_revision']
                    review.save(update_fields=['report', 'scanned_at', 'mapping_revision'])
                    ensure_numbering_checklist(review)
        if not report['bibles']:
            self.stderr.write(self.style.WARNING('No cached passage entries found; nothing can be verified.'))
        for warning in report['warnings']:
            self.stderr.write(self.style.WARNING(warning))
        findings = 0
        for result in report['bibles']:
            count = len(result['findings'])
            findings += count
            self.stdout.write(
                f"{result['bible_id']}: fresh={result['entries'].get('fresh', 0)} "
                f"expired={result['entries'].get('expired', 0)} "
                f"unknown_expiry={result['entries'].get('unknown_expiry', 0)} "
                f"untrusted_ttl={result['entries'].get('untrusted_ttl', 0)} "
                f"chapters={result['cached_chapters']} findings={count}"
            )
            for scope in ('psalms', 'hosea', 'joel'):
                coverage = result['scopes'][scope]
                self.stdout.write(
                    f"  {scope}: {coverage['state']} "
                    f"({coverage['cached_candidates']}/{coverage['expected_cases']} cached candidates)"
                )
        self.stdout.write('API requests: 0. Structural checks do not confirm verse numbering or verse boundaries.')
        if options['fail_on_findings'] and findings:
            raise CommandError(f'{findings} structural findings require review.')
