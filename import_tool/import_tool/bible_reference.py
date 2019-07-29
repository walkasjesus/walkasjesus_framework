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

        pattern = r'(.*) (\d+):(\d+)-?(\d+)?:?(\d+)?'
        # translate things like 1 Joh 2:1-3
        match = re.match(pattern, verse_string)
        groups = match.groups()

        reference.start_chapter = int(groups[1])
        reference.start_verse = int(groups[2])
        reference.end_chapter = int(reference.start_chapter)
        reference.end_verse = int(reference.start_verse)

        # Extra verse like 1:2-3
        if groups[3] is not None and groups[4] is None:
            reference.end_verse = int(groups[3])

        # Extra chapter like 1:2-2:3
        if groups[3] is not None and groups[4] is not None:
            reference.end_chapter = int(groups[3])
            reference.end_verse = int(groups[4])

        return reference
