import json
from unittest import TestCase, skip

from bible_api_client import BibleApiClient
from tests.dummy_responses import DummyResponses


@skip('Only used for development')
class ManualQueriesTest(TestCase):
    def test_list_books(self):
        response_string = DummyResponses().books()
        books = json.loads(response_string)['data']
        for book in books:
            print(book['id'])

    def test_query(self):
        #response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/books/dag/chapters')
        response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/verses/DAG.2.4')
        print(response_string)
        entries = json.loads(response_string)['data']
        self.assertTrue(True)
