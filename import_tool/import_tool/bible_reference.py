import re

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

        pattern = r'(.*) (\d+):(\d+)-?(\d+)?'
        # translate things like 1 Joh 2:1-3
        match = re.match(pattern, verse_string)
        groups = match.groups()

        if len(groups) > 3:
            reference.start_chapter = groups[1]
            reference.start_verse = groups[2]
            reference.end_chapter = reference.start_chapter
        if groups[3] is None:
            reference.end_verse = reference.start_verse
        else:
            reference.end_verse = groups[3]

        return reference
