from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.simple_cache import SimpleCache


def write_cache_entry(path, key):
    SimpleCache(Path(path)).set_value(key, key)


class TestSimpleCache(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.cache_path = Path(self.directory.name) / 'cache.json'

    def test_get(self):
        cache = SimpleCache(self.cache_path)
        method = Mock(return_value='my_value')

        for i in range(5):
            cached_value = cache.get(method, 'arg')

        self.assertEqual(cached_value, 'my_value')
        self.assertEqual(method.call_count, 1)

    def test_get_with_lambda_notation(self):
        cache = SimpleCache(self.cache_path)
        cached_value = cache.get(lambda f: f * f, 5)
        self.assertEqual(cached_value, 25)

    def test_load_and_store(self):
        cache = SimpleCache(self.cache_path)
        cache.get(lambda f: f, 'test')
        cache.get(lambda f: f, 'another_value')
        cache.get(lambda f: f*f, 5)

        cache_before_load = cache._cache
        cache.store_state()

        # Make a new cache to really test restore mechanism
        cache = SimpleCache(self.cache_path)
        cache.load_state()
        cache_after_load = cache._cache

        self.assertEqual(cache_before_load, cache_after_load)

    def test_separate_instances_merge_updates_and_observe_deletions(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.json'
            prefetch = SimpleCache(path)
            server = SimpleCache(path)
            prefetch.set_value('chapter', 'text')
            server.set_value('other', 'value')
            self.assertEqual(SimpleCache(path).get_value('chapter'), 'text')
            self.assertEqual(server.get_value('chapter'), 'text')
            prefetch.clear_key('chapter')
            server.store_state()
            self.assertNotIn('chapter', SimpleCache(path))
            self.assertIsNone(server.get_value('chapter'))

    def test_concurrent_processes_do_not_lose_entries(self):
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / 'cache.json')
            with ProcessPoolExecutor(max_workers=4) as executor:
                list(executor.map(write_cache_entry, [path] * 16, [str(i) for i in range(16)]))
            self.assertEqual(set(SimpleCache(Path(path)).cached_keys()), {str(i) for i in range(16)})

    def test_invalid_disk_cache_is_not_overwritten(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.json'
            path.write_text('{')
            with self.assertLogs(level='WARNING'):
                cache = SimpleCache(path)
                cache.set_value('new', 'value')
            self.assertEqual(path.read_text(), '{')
            self.assertEqual(cache.cache_items_not_persisted, 1)

    def test_failed_refresh_keeps_existing_cached_value(self):
        with TemporaryDirectory() as directory:
            cache = SimpleCache(Path(directory) / 'cache.json')
            cache.set_value('url', 'old')
            client = CachedBibleApiClient('test')
            client.cache = cache
            with patch('bible_lib.bible_api.bible_api_client.BibleApiClient.get',
                       side_effect=RuntimeError('API failure')):
                with self.assertRaisesRegex(RuntimeError, 'API failure'):
                    client.refresh('url')
            self.assertEqual(SimpleCache(cache.cache_path).get_value('url'), 'old')
