from bible_lib.bible_api.bible_api_client import BibleApiClient
from bible_lib.bible_api.services import Services


class CachedBibleApiClient(BibleApiClient):
    def __init__(self):
        super(CachedBibleApiClient, self).__init__()
        self.cache = Services().cache

    def get(self, url: str):
        return self.cache.get(super(CachedBibleApiClient, self).get, url)
