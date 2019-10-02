from bible_lib import Bible
from bible_lib.bible_api.api_bibles import ApiBibles


class BibleFactory:
    def __init__(self, api_key):
        self.api_key = api_key

    def all(self) -> {}:
        """" Return a dictionary with key:bible_id, value:Bible. """
        bibles = ApiBibles(self.api_key).dictionary()

        return bibles

    def create(self, bible_id: str) -> Bible:
        """ Create a new bible given the bible id. """
        all_bibles = self.all()

        if bible_id in all_bibles:
            return all_bibles[bible_id]

        raise KeyError(f'Bible {bible_id} not found')
