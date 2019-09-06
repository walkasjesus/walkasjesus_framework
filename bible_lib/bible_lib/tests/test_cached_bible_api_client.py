from unittest import TestCase
from unittest.mock import Mock

from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient


class TestCachedBibleApiClient(TestCase):
    def test_get(self):
        cache_api = CachedBibleApiClient()
        cache_api.cache.get = Mock()
        self.assertEqual(cache_api.cache.get.call_count, 0)
        cache_api.get('url/1')
        self.assertEqual(cache_api.cache.get.call_count, 1)
