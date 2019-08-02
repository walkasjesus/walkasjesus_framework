import json
import zipfile

from bible_lib import BibleBooks, _DATA_PATH
from bible_lib.bible import Bible


class HsvBible(Bible):
    # share variable between HsvBible
    _content = None

    def __init__(self):
        self.id = 'HSV'
        self.name = 'Herziene Staten Vertaling'
        self.language = 'nl'

        # Do not load if already done by another instance
        if HsvBible._content is None:
            HsvBible._content = self._load()

    def _load(self):
        with zipfile.ZipFile(_DATA_PATH / 'hsv_bible.zip', mode='r') as zip_file:
            json_content = zip_file.read('hsv_bible.json', pwd='bible'.encode()).decode('utf-8')
            return json.loads(json_content)

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:

        verses_texts = []
        current_chapter = start_chapter
        current_verse = start_verse

        while current_chapter <= end_chapter:
            while self._contains(book, current_chapter, current_verse) and not (current_chapter >= end_chapter and current_verse > end_verse):
                verses_texts.append(self._get(book, current_chapter, current_verse))
                current_verse += 1

            current_chapter += 1
            current_verse = 1

        # TODO inject verse numbers with span like other interface

        return ' '.join(verses_texts)

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
