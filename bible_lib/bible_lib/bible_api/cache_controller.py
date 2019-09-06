from bible_lib import BibleBooks
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.simple_cache import SimpleCache


class CacheController:
    def __init__(self, cache: SimpleCache):
        self.cache = cache
        self.query_builder = QueryBuilder()

    def contains_verses(self,
                        bible_id: str,
                        book: BibleBooks,
                        start_chapter: int,
                        start_verse: int,
                        end_chapter: int,
                        end_verse: int) -> str:
        url = self.query_builder.get_verses(bible_id, book, start_chapter, start_verse, end_chapter, end_verse)
        return url in self.cache

    def clear_bible(self, bible_id: str):
        for key in self.cache.cached_keys():
            if f'/{bible_id}/' in key:
                self.cache.clear_key(key)

    def clear_bible_list(self):
        self.cache.clear_key(self.query_builder.get_bibles())

    def persist_cache(self):
        self.cache.store_state()
