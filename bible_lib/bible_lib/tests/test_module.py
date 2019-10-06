from pathlib import Path
from unittest import TestCase, skip

from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_api.services import Services
from bible_lib.bible_books import BibleBooks
from bible_lib.bible_api.api_bibles import ApiBibles
from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient


@skip('Only run module test manually as it connects to external API')
class TestModule(TestCase):
    def test_list_bibles(self):
        bibles = ApiBibles()
        bible_list = bibles.list()
        self.assertEqual(116, len(bible_list))

    def test_get_verse(self):
        bible = ApiBible('ead7b4cc5007389c-01')
        verse = bible.verse(BibleBooks.John, 3, 16)
        self.assertIn('Want zo lief heeft God de wereld gehad', verse)

    def test_caching_get(self):
        bible = ApiBible('ead7b4cc5007389c-01')

        for i in range(5):
            bible.verse(BibleBooks.John, 3, 16)

        internal_cache = bible.client.cache

        self.assertEqual(1, internal_cache.cache_misses)
        self.assertEqual(4, internal_cache.cache_hits)

    def test_caching_persist(self):
        # every store_cache_every_number_of_hits missed items we store to disk,
        # so we can reuse without connecting to the api

        bible = ApiBible('ead7b4cc5007389c-01')

        cache_location = bible.client.cache_location
        if cache_location.exists():
            cache_location.unlink()

        bible.verse(BibleBooks.John, 3, 1)

        Services().cache.store_state()

        self.assertTrue(cache_location.exists())

    def test_caching_restore(self):
        # every store_cache_every_number_of_hits missed items we store to disk,
        # so we can reuse without connecting to the api

        bible = ApiBible('ead7b4cc5007389c-01')

        # Use our client with an existing test cache
        client = CachedBibleApiClient(Path('data') / 'bible_api_cache.json')
        bible.client = client

        for i in range(1, store_cache_every_number_of_hits+1):
            bible.verse(BibleBooks.John, 3, i)

        self.assertEqual(0, bible.client.cache.cache_misses)
