import json
from unittest import TestCase, skip

from bible_lib.bible import Bible
from bible_lib.bible_api_client import BibleApiClient
from bible_lib.bible_books import BibleBooks
from bible_lib.tests.dummy_responses import DummyResponses


@skip('Only used for development')
class ManualQueriesTest(TestCase):
    def test_list_books(self):
        response_string = DummyResponses().books()
        books = json.loads(response_string)['data']
        for book in books:
            print(book['id'])

    def test_verse(self):
        bible = Bible('ead7b4cc5007389c-01')
        verse = bible.verse(BibleBooks.Genesis, 2, 12)
        print(verse)

    def test_query(self):
        #response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/books/dag/chapters')
        #response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/verses/DAG.2.4')
        #response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/search?query=MAT.5.43-44')
        #response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/search?query=JHN.1.51-2.1')
        response_string = BibleApiClient().get('bibles/ead7b4cc5007389c-01/passages/JHN.1.51-JHN.2.1')
        print(response_string)
        entries = json.loads(response_string)['data']
        self.assertTrue(True)
