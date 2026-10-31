import gzip
import json
from pathlib import Path

from django.core.management import BaseCommand, CommandError
from django.conf import settings

from walkasjesus_app.models import BibleTranslation
from walkasjesus_app.models.bible_books import BibleBooks
from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _load_chapter_index,
    _save_chapter_index,
    build_bible_study_chapter_index_for_bibles,
)


class Command(BaseCommand):
    help = 'Build a local Bible Study chapter index (bible -> book -> chapter -> max verse).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--local-kjv',
            action='store_true',
            help='Build the complete primary KJV index from bundled tagged KJV data without API calls.',
        )
        parser.add_argument(
            '--bible-id',
            action='append',
            dest='bible_ids',
            default=[],
            help='Optional bible ID to build. Repeat for multiple IDs.',
        )
        parser.add_argument(
            '--book',
            action='append',
            dest='books',
            default=[],
            help='Optional Bible book enum name (e.g. Genesis). Repeat for multiple books.',
        )

    def handle(self, *args, **options):
        if options['local_kjv']:
            if options['bible_ids'] or options['books']:
                raise CommandError('--local-kjv builds the complete primary index; do not combine with --book or --bible-id.')
            primary_id = str(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_PRIMARY_BIBLE_ID', '') or '').strip()
            if primary_id not in {'de4e12af7f28f599-01', 'de4e12af7f28f599-02'}:
                raise CommandError('--local-kjv requires a King James Version primary index Bible.')
            root = Path(settings.BASE_DIR) / 'data' / 'tagged_bibles' / 'kjv'
            bible_index = {}
            for book_name, chapter_count in _CANONICAL_CHAPTER_COUNTS.items():
                path = root / f'{book_name}.json.gz'
                if not path.exists():
                    raise CommandError(f'Missing tagged KJV data: {path}. Initialize the tagged_bibles submodule.')
                with gzip.open(path, 'rt', encoding='utf-8') as handle:
                    chapters = json.load(handle)['chapters']
                if set(chapters) != {str(chapter) for chapter in range(1, chapter_count + 1)}:
                    raise CommandError(f'Incomplete chapter data for {book_name}.')
                bible_index[book_name] = {
                    chapter: max(int(verse) for verse in verses)
                    for chapter, verses in chapters.items()
                }
            index = _load_chapter_index()
            index[primary_id] = bible_index
            _save_chapter_index(index)
            self.stdout.write(self.style.SUCCESS('Complete primary KJV chapter index built from local data (no API calls).'))
            return

        requested_ids = [str(bid).strip() for bid in (options.get('bible_ids') or []) if str(bid).strip()]
        requested_books = [str(book).strip() for book in (options.get('books') or []) if str(book).strip()]
        if not requested_books:
            default_books = getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_DEFAULT_BOOKS', []) or []
            requested_books = [str(book).strip() for book in default_books if str(book).strip()]

        valid_book_names = {b.name for b in BibleBooks}
        unknown_books = sorted([book for book in requested_books if book not in valid_book_names])
        if unknown_books:
            self.stdout.write(self.style.ERROR(f'Unknown book name(s): {", ".join(unknown_books)}'))
            self.stdout.write('Use enum names from walkasjesus_app.models.bible_books.BibleBooks, e.g. Genesis, John.')
            return

        all_bibles = BibleTranslation().all_in_supported_languages()

        if requested_ids:
            bibles = [b for b in all_bibles if b.id in requested_ids]
            missing = sorted(set(requested_ids) - {b.id for b in bibles})
            if missing:
                self.stdout.write(self.style.WARNING(f'Skipping unknown bible IDs: {", ".join(missing)}'))
        else:
            primary_id = str(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_PRIMARY_BIBLE_ID', '') or '').strip()
            if not primary_id:
                primary_id = str(getattr(settings, 'DEFAULT_BIBLE_ANY_LANGUAGE', '') or '').strip()
            bibles = [b for b in all_bibles if b.id == primary_id] if primary_id else []
            if not bibles:
                self.stdout.write(
                    self.style.WARNING(
                        f'Primary index bible {primary_id or "<unset>"} not available; nothing to build.'
                    )
                )
                return

        if not bibles:
            self.stdout.write(self.style.WARNING('No bibles selected; nothing to build.'))
            return

        if requested_books:
            self.stdout.write(
                f'Building Bible Study chapter index for {len(bibles)} bible(s), '
                f'book(s): {", ".join(requested_books)}...'
            )
        else:
            self.stdout.write(f'Building Bible Study chapter index for {len(bibles)} bible(s)...')

        build_bible_study_chapter_index_for_bibles(bibles, only_books=requested_books or None)
        self.stdout.write(self.style.SUCCESS('Bible Study chapter index build completed.'))
