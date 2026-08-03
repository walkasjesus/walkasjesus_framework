from unittest import TestCase

from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_books import BibleBooks


class TestQueryBuilder(TestCase):
    def test_get_verses_supports_esther(self):
        url = QueryBuilder().get_verses('bible_id', BibleBooks.Esther, 1, 1, 1, 1)

        self.assertIn('/passages/EST.1.1-EST.1.1?', url)

    def test_get_verses_keeps_alternative_daniel_key(self):
        url = QueryBuilder().get_verses('ead7b4cc5007389c-01', BibleBooks.Daniel, 1, 1, 1, 1)

        self.assertIn('/passages/DAG.1.1-DAG.1.1?', url)