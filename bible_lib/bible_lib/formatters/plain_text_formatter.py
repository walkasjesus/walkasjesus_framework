from bible_lib.formatters.formatter import Formatter


class PlainTextFormatter(Formatter):
    def flush(self):
        texts = [v.text for v in self.verses_buffer]
        formatted = ' '.join(texts)
        self.verses_buffer = []
        return formatted
