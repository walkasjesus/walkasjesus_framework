from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from file_cache import SimpleCache


class TestSimpleCache(TestCase):
    def test_get(self):
        cache = SimpleCache()
        method = Mock(return_value='my_value')

        for i in range(5):
            cached_value = cache.get(method, 'arg')

        self.assertEqual(cached_value, 'my_value')
        self.assertEqual(method.call_count, 1)

    def test_get_with_lambda_notation(self):
        cache = SimpleCache()
        cached_value = cache.get(lambda f: f * f, 5)
        self.assertEqual(cached_value, 25)

    def test_load_and_store(self):
        cache_path = Path('cache.json')

        cache = SimpleCache()
        cache.get(lambda f: f, 'test')
        cache.get(lambda f: f, 'another_value')
        cache.get(lambda f: f*f, 5)

        cache_before_load = cache._cache
        cache.store_state(cache_path)

        # Make a new cache to really test restore mechanism
        cache = SimpleCache()
        cache.load_state(cache_path)
        cache_after_load = cache._cache

        # Clean up file
        cache_path.unlink()

        self.assertEqual(cache_before_load, cache_after_load)
