from unittest import TestCase
from unittest.mock import Mock

from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.config import store_cache_every_number_of_hits


class TestCachedBibleApiClient(TestCase):
    def test_get(self):
        cache_api = CachedBibleApiClient()
        cache_api.cache.get = Mock()
        self.assertEqual(cache_api.cache.get.call_count, 0)
        cache_api.get('url/1')
        self.assertEqual(cache_api.cache.get.call_count, 1)

    def test_persist_cache(self):
        cache_api = CachedBibleApiClient()
        cache_api.cache.get = Mock()
        cache_api.cache.store_state = Mock()

        cache_api.cache.cache_items_not_persisted = store_cache_every_number_of_hits - 1
        cache_api.get('url/1')
        self.assertEqual(cache_api.cache.store_state.call_count, 0)
        cache_api.cache.cache_items_not_persisted = store_cache_every_number_of_hits
        cache_api.get('url/2')
        self.assertEqual(cache_api.cache.store_state.call_count, 1)
