import json
import logging
import zipfile

from bible_lib import _DATA_PATH
from bible_lib.bible import Bible
from bible_lib.bible_books import BibleBooks
from bible_lib.performance_time_decorator import performance_time
from bible_lib.formatters.formatter import Formatter
from bible_lib.formatters.plain_text_formatter import PlainTextFormatter
from bible_lib.verse import Verse


class HsvBible(Bible):
    # share variable between HsvBible
    _content = None

    def __init__(self, text_formatter: Formatter = PlainTextFormatter()):
        self.id = 'hsv'
        self.name = 'Herziene Staten Vertaling'
        self.language = 'nl'
        self.formatter = text_formatter
        self.copyright = 'All scripture quotations in this publication are from the Herziene Statenvertaling, © Stichting HSV 2010. This bible references are online available at www.herzienestatenvertaling.nl. We are very grateful to the creators of these translations for the online availability of Bible texts and search functionality.'

        # Do not load if already done by another instance
        if HsvBible._content is None:
            HsvBible._content = self._load()

    @performance_time
    def _load(self):
        logging.getLogger().info('Loading HSV bible contents from disk')
        with zipfile.ZipFile(_DATA_PATH / 'hsv_bible.zip', mode='r') as zip_file:
            json_content = zip_file.read('hsv_bible.json', pwd='bible'.encode()).decode('utf-8')
            return json.loads(json_content)

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:

        current_chapter = start_chapter
        current_verse = start_verse

        while current_chapter <= end_chapter:
            while self._contains(book, current_chapter, current_verse) and not (
                    current_chapter >= end_chapter and current_verse > end_verse):
                verse = Verse(book,
                              current_chapter,
                              current_verse,
                              self._get(book, current_chapter, current_verse))
                self.formatter.add_verse(verse)
                current_verse += 1

            current_chapter += 1
            current_verse = 1

        return self.formatter.flush()

    def _get(self, book: BibleBooks, chapter: int, verse: int) -> bool:
        return HsvBible._content[book.name][str(chapter)][str(verse)]

    def _contains(self, book: BibleBooks, chapter: int, verse: int) -> bool:
        book_key = book.name
        if book_key not in HsvBible._content:
            return False
        if str(chapter) not in HsvBible._content[book_key]:
            return False
        if str(verse) not in HsvBible._content[book_key][str(chapter)]:
            return False

        return True
