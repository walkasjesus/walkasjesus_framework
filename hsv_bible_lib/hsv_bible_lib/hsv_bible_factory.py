from bible_lib import Bibles, Bible

from hsv_bible_lib.bible_hsv.hsv_bible import HsvBible


class HsvBibleFactory:
    def create(self, bible_id: str) -> Bible:
        all_bibles = Bibles().dictionary()

        if bible_id == 'hsv':
            return HsvBible()

        if bible_id in all_bibles:
            return all_bibles[bible_id]

        raise KeyError(f'Bible {bible_id} not found')
