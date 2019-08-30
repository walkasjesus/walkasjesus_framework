from unittest import TestCase

from bible_lib.bible_api.cache_controller import CacheController
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_books import BibleBooks
from bible_lib.simple_cache import SimpleCache


class TestCacheController(TestCase):
    def test_clear_bible(self):
        cache = SimpleCache()
        controller = CacheController(cache)
        # By calling get the cache is filled with the given url
        cache.get(lambda x: 'test_value', QueryBuilder().get_verses('bible_id', BibleBooks.Proverbs, 1, 1, 2, 2))
        cache.get(lambda x: 'test_value', QueryBuilder().get_verses('bible_id_2', BibleBooks.Proverbs, 1, 1, 2, 2))

        self.assertTrue(controller.contains_verses('bible_id', BibleBooks.Proverbs, 1, 1, 2, 2))
        controller.clear_bible('bible_id')
        self.assertFalse(controller.contains_verses('bible_id', BibleBooks.Proverbs, 1, 1, 2, 2))
        self.assertTrue(controller.contains_verses('bible_id_2', BibleBooks.Proverbs, 1, 1, 2, 2))

    def test_clear_bible_list(self):
        cache = SimpleCache()
        controller = CacheController(cache)

        key = QueryBuilder().get_bibles()

        # By calling get the cache is filled with the given url
        cache.get(lambda x: 'test_value', key)

        self.assertIn(key, cache)
        controller.clear_bible_list()
        self.assertNotIn(key, cache)

