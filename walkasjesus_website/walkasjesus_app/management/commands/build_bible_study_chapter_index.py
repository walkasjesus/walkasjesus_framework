from django.core.management import BaseCommand
from django.conf import settings

from walkasjesus_app.models import BibleTranslation
from walkasjesus_app.models.bible_books import BibleBooks
from walkasjesus_app.views.bible_study_view import build_bible_study_chapter_index_for_bibles


class Command(BaseCommand):
    help = 'Build a local Bible Study chapter index (bible -> book -> chapter -> max verse).'

    def add_arguments(self, parser):
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
