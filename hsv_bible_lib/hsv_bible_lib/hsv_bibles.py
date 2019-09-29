from bible_lib import Bibles
from hsv_bible_lib.bible_hsv.hsv_bible import HsvBible


class HsvBibles(Bibles):

    def dictionary(self) -> {}:
        """ Return a dictionary with key:Bible """
        bibles = super().dictionary()
        hsv_bible = HsvBible()
        bibles[hsv_bible.id] = hsv_bible

        return bibles
