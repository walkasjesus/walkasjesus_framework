import time
from pathlib import Path

from bible_lib.bible_api.bible_api_client import BibleApiClient
from bible_lib.config import store_cache_every_number_of_hits
from bible_lib.performance_time_decorator import performance_time
from bible_lib.simple_cache import SimpleCache


class CachedBibleApiClient(BibleApiClient):
    @performance_time
    def __init__(self, cache_location: Path = Path('bible_api_cache.json')):
        super(CachedBibleApiClient, self).__init__()
        self.cache = SimpleCache()
        self.cache_location = cache_location
        self.cache.load_state(self.cache_location)
        self._last_store_state_time = 0

    def get(self, url: str):
        # Very simple mechanism to store the cache contents
        if self.cache.cache_items_not_persisted >= store_cache_every_number_of_hits and \
                self.time_since_last_store_state() > 60:
            self.cache.store_state(self.cache_location)
            self._last_store_state_time = time.time()

        return self.cache.get(super(CachedBibleApiClient, self).get, url)

    def time_since_last_store_state(self):
        return time.time() - self._last_store_state_time
