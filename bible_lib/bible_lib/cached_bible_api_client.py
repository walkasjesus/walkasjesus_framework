from bible_api_client import BibleApiClient
from file_cache import SimpleCache


class CachedBibleApiClient(BibleApiClient):
    def __init__(self):
        self.client = BibleApiClient()
        self.cache = SimpleCache()

    def get(self, relative_path: str):
        # Very simple mechanism to store the cache contents
        if self.cache.cache_items_not_persisted >= 10:
            self.cache.store_state()

        return self.cache.get(relative_path,
                              super(CachedBibleApiClient, self).get)
