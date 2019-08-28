from bible_lib.verse import Verse


class Formatter:
    def __init__(self):
        self.verses_buffer = []

    def add_verse(self, verse: Verse):
        self.verses_buffer.append(verse)

    def flush(self):
        pass
