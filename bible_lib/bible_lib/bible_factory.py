from bible_lib import Bible
from bible_lib.api_bible import ApiBible
from bible_lib.hsv_bible import HsvBible


class PlainTextFormatter(object):
    pass


class BibleFactory:
    def __init__(self, text_formatter=PlainTextFormatter()):
        self.text_formatter = text_formatter

    def create(self, bible_id: str, ) -> Bible:
        if bible_id.lower() == 'hsv':
            return HsvBible(self.text_formatter)
        else:
            return ApiBible(bible_id=bible_id, self.text_formatter)

