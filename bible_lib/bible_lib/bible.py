from bible_lib.bible_books import BibleBooks


class Bible:
    def __init__(self, bible_id=None):
        self.id = bible_id
        self.name = ''
        self.language = ''
        
    def verse(self,
              book:
              BibleBooks,
              chapter: int,
              verse: int) -> str:
        return self.verses(book, chapter, verse, chapter, verse)

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:
        pass
