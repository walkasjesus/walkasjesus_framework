from unittest import TestCase
from unittest.mock import Mock

from cached_bible_api_client import CachedBibleApiClient


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

        cache_api.cache.cache_items_not_persisted = 9
        cache_api.get('url/1')
        self.assertEqual(cache_api.cache.store_state.call_count, 0)
        cache_api.cache.cache_items_not_persisted = 10
        cache_api.get('url/2')
        self.assertEqual(cache_api.cache.store_state.call_count, 1)

    def test_singleton(self):
        """" Because we do not want every new client to begin its own cache
        and disrupt other caches, we use a singleton to ensure we only have one object.
        This is not the most elegant solution, but it is simple and enough for now."""
        cache_api_1 = CachedBibleApiClient()
        cache_api_2 = CachedBibleApiClient()

        cache_api_1.temp_var = 1
        cache_api_2.temp_var = 2

        self.assertEqual(cache_api_1.temp_var, cache_api_2.temp_var)
