from bible_lib.formatters.formatter import Formatter


class PlainTextFormatter(Formatter):
    def __init__(self):
        self.buffer = []

    def add_verse(self, chapter, verse, text):
        self.buffer.append(text)

    def flush(self):
        formatted = ' '.join(self.buffer)
        self.buffer.clear()
        return formatted
