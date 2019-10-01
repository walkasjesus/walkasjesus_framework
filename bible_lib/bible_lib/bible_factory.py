from bible_lib import Bible, settings
from bible_lib.bible_api.api_bibles import ApiBibles
from bible_lib.bible_hsv.hsv_bible import HsvBible


class BibleFactory:
    def all(self) -> {}:
        """" Return a dictionary with key:bible_id, value:Bible. """
        bibles = ApiBibles().dictionary()

        if settings.HSV_BIBLE_KEY != '':
            bibles['hsv'] = HsvBible()

        return bibles

    def create(self, bible_id: str) -> Bible:
        """ Create a new bible given the bible id. """
        all_bibles = self.all()

        if bible_id in all_bibles:
            return all_bibles[bible_id]

        raise KeyError(f'Bible {bible_id} not found')
