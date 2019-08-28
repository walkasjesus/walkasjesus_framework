from bible_lib.bible_books import BibleBooks


class Verse:
    def __init__(self,
                 book: BibleBooks = BibleBooks.Genesis,
                 chapter: int = 0,
                 verse: int = 0,
                 text: str = ''
                 ):
        self.book = book
        self.chapter = chapter
        self.verse = verse
        self.text = text
