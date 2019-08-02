from bible_lib import Bible
from bible_lib.api_bible import ApiBible
from bible_lib.hsv_bible import HsvBible


class BibleFactory:
    def create(self, bible_id: str) -> Bible:
        if bible_id.lower() == 'hsv':
            return HsvBible()
        else:
            return ApiBible(bible_id=bible_id)
