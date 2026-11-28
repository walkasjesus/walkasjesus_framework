from bible_lib.bible_books import BibleBooks
from typing import Optional


class Verse:
    def __init__(self,
                 book: BibleBooks = BibleBooks.Genesis,
                 chapter: int = 0,
                 verse: int = 0,
                 text: str = '',
                 end_verse: Optional[int] = None
                 ):
        self.book = book
        self.chapter = chapter
        self.verse = verse
        self.end_verse = verse if end_verse is None else end_verse
        self.text = text
