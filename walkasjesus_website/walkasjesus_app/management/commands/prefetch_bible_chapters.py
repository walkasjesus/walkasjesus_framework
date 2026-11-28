"""Prefetch and refresh whole Bible chapters in the api.bible cache.

Intended to run daily from cron. Each run refreshes at most ``--max-requests``
chapter passages, so a complete refresh cycle is spread out over multiple days
while every cached entry is renewed before the 25-day cache TTL expires
(api.bible terms require refreshing cached content at least every 30 days).

Only translations without a per-translation license verse limit are prefetched;
license-limited translations (e.g. NBV21/BGT, max 5 verses at a time) are never
bulk-fetched and remain on-demand only.
"""
import time

from bible_lib import BibleBooks as BibleLibBibleBooks
from bible_lib.bible_api.services import Services
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from walkasjesus_app.lib.bible_chapter_prefetch import chapters_for_book, max_display_verse
from walkasjesus_app.lib.bible_display_limits import max_verses_for_bible_id
from walkasjesus_app.models import BibleTranslation
from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _fetch_chapter_verse_texts,
    _study_chapter_source_plan,
)


class Command(BaseCommand):
    help = 'Prefetch/refresh whole Bible chapters (api.bible) within the daily request budget.'

    def add_arguments(self, parser):
        parser.add_argument('--bible-ids', nargs='*', default=None,
                            help='Bible ids to prefetch, in priority order. Default: '
                                 'settings.BIBLE_PREFETCH_BIBLE_IDS, or Dutch, KJV, Messianic/Jewish, '
                                 'then other eligible translations.')
        parser.add_argument('--books', nargs='*', default=None,
                            help='Limit to these Bible book names, in priority order (e.g. John Genesis).')
        parser.add_argument('--max-requests', type=int,
                            default=int(getattr(settings, 'BIBLE_PREFETCH_MAX_REQUESTS_PER_RUN', 300)),
                            help='Maximum number of api.bible requests for this run.')
        parser.add_argument('--refresh-margin-days', type=float, default=5.0,
                            help='Refresh cached chapters that expire within this many days.')
        parser.add_argument('--sleep', type=float, default=0.7,
                            help='Seconds to sleep between api.bible requests.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Only report which chapters would be refreshed.')

    def handle(self, *args, **options):
        bibles = self._target_bibles(options['bible_ids'])
        if not bibles:
            self.stdout.write(self.style.WARNING('No eligible bibles to prefetch.'))
            return

        requested_books = options['books'] or list(_CANONICAL_CHAPTER_COUNTS)
        invalid_books = [book for book in requested_books if book not in _CANONICAL_CHAPTER_COUNTS]
        if invalid_books:
            raise CommandError(f'Unknown Bible book(s): {", ".join(invalid_books)}')
        requested_books = list(dict.fromkeys(requested_books))
        margin_seconds = max(0.0, options['refresh_margin_days']) * 86400
        max_requests = max(0, options['max_requests'])
        sleep_seconds = max(0.0, options['sleep'])
        dry_run = options['dry_run']

        api_cache = Services().cache
        requests_made = 0
        chapters_refreshed = 0
        chapters_fresh = 0
        chapters_failed = 0

        for bible in bibles:
            if requests_made >= max_requests:
                break
            self.stdout.write(f'Prefetching bible {bible.id} ({bible.name})')
            for book_name in requested_books:
                if requests_made >= max_requests:
                    break
                for chapter in chapters_for_book(book_name):
                    if requests_made >= max_requests:
                        break
                    last_display_verse = max_display_verse(bible, book_name, chapter)
                    if not last_display_verse:
                        continue
                    verse_numbers = range(1, last_display_verse + 1)
                    _, last_verse_by_chapter = _study_chapter_source_plan(
                        bible, book_name, chapter, verse_numbers, 'hebrew')
                    if not last_verse_by_chapter:
                        continue

                    urls = [
                        bible.chapter_passage_url(BibleLibBibleBooks[book_name], source_chapter, last_verse)
                        for source_chapter, last_verse in sorted(last_verse_by_chapter.items())
                    ]
                    now = time.time()
                    needs_refresh = any(
                        api_cache.expires_at(url) is None or api_cache.expires_at(url) - now < margin_seconds
                        for url in urls
                    )
                    if not needs_refresh:
                        chapters_fresh += 1
                        continue

                    if dry_run:
                        self.stdout.write(f'  {bible.name} ({bible.id}): would refresh '
                                          f'{book_name} {chapter} ({len(urls)} request(s))')
                        requests_made += len(urls)
                        chapters_refreshed += 1
                        continue

                    try:
                        fetched = _fetch_chapter_verse_texts(
                            bible, book_name, chapter, verse_numbers, 'hebrew', force_refresh=True)
                    except Exception as ex:
                        self.stderr.write(f'  {bible.name} ({bible.id}): '
                                          f'failed to refresh {book_name} {chapter}: {ex}')
                        chapters_failed += 1
                        fetched = {}
                    requests_made += len(urls)
                    if fetched:
                        chapters_refreshed += 1
                        self.stdout.write(f'  {bible.name} ({bible.id}): refreshed '
                                          f'{book_name} {chapter} ({len(fetched)} verses)')
                    else:
                        chapters_failed += 1
                        self.stdout.write(self.style.WARNING(
                            f'  {bible.name} ({bible.id}): no verses for {book_name} {chapter}'))
                    if sleep_seconds:
                        time.sleep(sleep_seconds)

        api_cache.store_state()
        summary = (f'Done. requests={requests_made} refreshed={chapters_refreshed} '
                   f'fresh={chapters_fresh} failed={chapters_failed}')
        self.stdout.write(self.style.SUCCESS(f'[dry-run] {summary}' if dry_run else summary))

    def _target_bibles(self, bible_ids):
        translations = BibleTranslation()
        all_bibles = translations.all_in_supported_languages()
        if bible_ids:
            selected = [translations.get(bible_id) for bible_id in bible_ids]
            selected = [bible for bible in selected if bible]
        else:
            configured = list(getattr(settings, 'BIBLE_PREFETCH_BIBLE_IDS', []) or [])
            if configured:
                selected = [bible for bible in (translations.get(bid) for bid in configured) if bible]
            else:
                selected = sorted(all_bibles, key=self._default_priority)

        eligible = []
        for bible in selected:
            if getattr(bible, 'is_local_source', False) or not hasattr(bible, 'chapter_verses'):
                continue
            if max_verses_for_bible_id(getattr(bible, 'id', '')):
                # License-limited translations (e.g. NBV21/BGT) must not be bulk-fetched.
                self.stdout.write(self.style.WARNING(
                    f'Skipping {bible.name} ({bible.id}): license limits display to '
                    f'{max_verses_for_bible_id(bible.id)} verses at a time.'))
                continue
            eligible.append(bible)
        return eligible

    @staticmethod
    def _default_priority(bible):
        if str(getattr(bible, 'language', '') or '').lower() == 'nl':
            return 0
        if bible.id == 'de4e12af7f28f599-01':
            return 1
        name = str(getattr(bible, 'name', '') or '').lower()
        if 'messianic' in name or 'jewish' in name:
            return 2
        return 3
