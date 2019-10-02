from bible_lib import Bible
from bible_lib.bible_api.api_bibles import ApiBibles
from bible_lib.bible_hsv.hsv_bible import HsvBible


class BibleFactory:
    def __init__(self, api_key, hsv_bible_key='', hsv_bible_path=''):
        self.api_key = api_key
        self.hsv_bible_key = hsv_bible_key
        self.hsv_bible_path = hsv_bible_path

    def all(self) -> {}:
        """" Return a dictionary with key:bible_id, value:Bible. """
        bibles = ApiBibles(self.api_key).dictionary()

        if self.hsv_bible_key != '':
            bibles['hsv'] = HsvBible(self.hsv_bible_key, self.hsv_bible_path)

        return bibles

    def create(self, bible_id: str) -> Bible:
        """ Create a new bible given the bible id. """
        all_bibles = self.all()

        if bible_id in all_bibles:
            return all_bibles[bible_id]

        raise KeyError(f'Bible {bible_id} not found')
