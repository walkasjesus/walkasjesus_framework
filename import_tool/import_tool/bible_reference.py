from bible_lib.bible_books import BibleBooks


class BibleReference:
    def __init__(self):
        self.book = BibleBooks.Genesis
        self.start_chapter = 0
        self.start_verse = 0
        self.end_chapter = 0
        self.end_verse = 0

    @staticmethod
    def create_from_string(verse_string):
        reference = BibleReference()

        return reference