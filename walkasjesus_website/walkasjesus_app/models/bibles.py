import logging
import json
from pathlib import Path

from bible_lib import BibleFactory, Bible, BibleBooks as BibleLibBibleBooks
from django.db import models
from django.utils import translation

from walkasjesus_app.lib.access_policy import cjb_bible_id
from walkasjesus_website import settings


class LocalCompleteJewishBible(Bible):
    """Local NT-only CJB data source based on the bundled David Stern dataset."""

    _index = None

    def __init__(self, bible_id):
        super().__init__(bible_id=bible_id)
        self.name = str(getattr(settings, 'CJB_BIBLE_NAME', 'Complete Jewish Bible (David H. Stern, NT)')).strip()
        self.language = 'en'
        self.copyright = str(getattr(settings, 'DAVID_STERN_COMMENTARY_FOOTER_TEXT', '')).strip()

    @staticmethod
    def _normalize_book_key(value):
        return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())

    @classmethod
    def _load_index(cls):
        if cls._index is not None:
            return cls._index

        cls._index = {}
        data_path = Path(__file__).resolve().parents[3] / 'bible_lib' / 'sources' / 'jnt_bible_lib_compatible.json'

        if not data_path.exists():
            return cls._index

        try:
            with data_path.open('r', encoding='utf-8') as handle:
                payload = json.load(handle)
        except Exception:
            logging.getLogger().warning('Could not load local CJB source data.')
            return cls._index

        for book in payload.get('books', []):
            aliases = {
                book.get('bible_book'),
                book.get('bible_book_enum_name'),
                book.get('bible_book_abbreviation'),
                book.get('book_title_source'),
            }
            chapter_index = {}

            for chapter in book.get('chapters', []):
                try:
                    chapter_number = int(chapter.get('chapter_number'))
                except Exception:
                    continue

                verse_index = {}
                for verse in chapter.get('verses', []):
                    try:
                        verse_number = int(verse.get('verse'))
                    except Exception:
                        continue

                    text = str(verse.get('text', '')).strip()
                    if text:
                        verse_index[verse_number] = text

                if verse_index:
                    chapter_index[chapter_number] = verse_index

            if not chapter_index:
                continue

            for alias in aliases:
                normalized_alias = cls._normalize_book_key(alias)
                if normalized_alias:
                    cls._index[normalized_alias] = chapter_index

        return cls._index

    def verses(self, book: BibleLibBibleBooks, start_chapter: int, start_verse: int, end_chapter: int, end_verse: int) -> str:
        index = self._load_index()
        book_key = self._normalize_book_key(getattr(book, 'name', str(book)))
        chapter_index = index.get(book_key, {})

        if not chapter_index:
            return ''

        snippets = []
        for chapter in range(int(start_chapter), int(end_chapter) + 1):
            chapter_verses = chapter_index.get(chapter, {})
            if not chapter_verses:
                continue

            first_verse = int(start_verse) if chapter == int(start_chapter) else min(chapter_verses.keys())
            last_verse = int(end_verse) if chapter == int(end_chapter) else max(chapter_verses.keys())

            for verse_nr in range(first_verse, last_verse + 1):
                text = chapter_verses.get(verse_nr)
                if text:
                    snippets.append((chapter, verse_nr, text))

        if not snippets:
            return ''

        if len(snippets) == 1:
            return snippets[0][2]

        return '\n'.join(f'{chapter}:{verse} {text}' for chapter, verse, text in snippets)


class BibleTranslation:
    """" Get a specific (set of) bible translation(s). """
    _bible_factory = BibleFactory(settings.BIBLE_API_KEY)

    @staticmethod
    def _build_all_bibles():
        bibles = BibleTranslation._bible_factory.all()
        local_cjb_id = cjb_bible_id()
        if local_cjb_id and local_cjb_id not in bibles:
            bibles[local_cjb_id] = LocalCompleteJewishBible(local_cjb_id)
        return bibles

    _all_bibles = {}

    def all(self) -> [Bible]:
        """" Get all bible translations (including languages not supported this website). """
        return list(BibleTranslation._all_bibles.values())

    def all_enabled(self) -> [Bible]:
        """ This will list all bibles that are not explicitly disabled,
        so if information is missing it will assume them to be enabled. """
        enabled = set(self.all()) - set(self.all_disabled())
        for bible_id in getattr(settings, 'FORCE_ENABLED_BIBLE_TRANSLATIONS', []):
            if self.contains(bible_id):
                enabled.add(self.get(bible_id))
        return enabled

    def all_disabled(self) -> [Bible]:
        """ This will return all bibles that are explicitly disabled. """
        return [BibleTranslation._bible_factory.create(m.bible_id)
                for m in BibleTranslationMetaData.objects.all()
                if m.is_enabled is False]

    def all_in_user_language(self) -> [Bible]:
        """" Get all bibles in the user main language. """
        current_user_language = translation.get_language()
        return [b for b in self.all_enabled() if b.language == current_user_language]

    def all_in_supported_languages(self):
        """" Get all bibles in translations supported by this website. """
        languages = [code for code, name in settings.LANGUAGES]
        return [b for b in self.all_enabled() if b.language in languages]

    def count(self):
        return len(self.all_enabled())

    def get(self, bible_id: str):
        """" Get a specific bible translation given its unique id. """
        if bible_id not in BibleTranslation._all_bibles:
            logging.getLogger().warning(f'Failed to retrieve bible with id {bible_id}.')
            return Bible("no bible found")
        else:
            return BibleTranslation._all_bibles[bible_id]

    def contains(self, bible_id: str):
        return bible_id in BibleTranslation._all_bibles


class BibleTranslationMetaData(models.Model):
    """ While the BibleTranslation itself is dynamically retrieved from the library,
    we want some extra information stored in the database, like if we want to enable it or not. """
    bible_id = models.CharField(max_length=32, unique=True, null=False, default='')
    is_enabled = models.BooleanField(default=True)


BibleTranslation._all_bibles = BibleTranslation._build_all_bibles()
