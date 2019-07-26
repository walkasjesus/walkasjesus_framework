from pathlib import Path

from bible_api_client import BibleApiClient
from simple_cache import SimpleCache


class CachedBibleApiClient(BibleApiClient):
    def __init__(self, cache_location: Path = Path('bible_api_cache.json')):
        super(CachedBibleApiClient, self).__init__()
        self.cache = SimpleCache()
        self.cache_location = cache_location
        self.cache.load_state(self.cache_location)

    def get(self, relative_path: str):
        # Very simple mechanism to store the cache contents
        if self.cache.cache_items_not_persisted >= 10:
            self.cache.store_state(self.cache_location)

        return self.cache.get(super(CachedBibleApiClient, self).get, relative_path)
