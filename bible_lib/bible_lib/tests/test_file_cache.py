from pathlib import Path
from unittest import TestCase

from file_cache import FileCache


class TestFileCache(TestCase):
    def test_get_and_set(self):
        cache = FileCache(Path('cache.json'))
        cache.set('my_key', 'my_value')
        cached_value = cache.get('my_key')

        self.assertEqual('my_value', cached_value)

    def test_load_and_store(self):
        cache_path = Path('cache.json')

        cache = FileCache(cache_path)
        cache.set('my_key', 'my_value')
        cache.set('key_2', 'another_value')

        cache_before_load = cache._cache

        cache.store_state()

        # Make a new cache to really test restore mechanism
        cache = FileCache(cache_path)

        cache.load_state()

        self.assertEqual(cache_before_load, cache._cache)
