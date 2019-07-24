import json
from unittest import TestCase
from unittest.mock import Mock

from bible_api_client import BibleApiClient
from bibles import Bibles
from tests.dummy_responses import DummyResponses


class TestBibles(TestCase):
    def test_list_biblesa(self):
        response_string = DummyResponses().books()
        books = json.loads(response_string)['data']
        for book in books:
            print(book['id'])


    def test_list_bibles(self):
        bibles = Bibles()
        bibles.client.get = Mock(return_value=DummyResponses().bibles())
        bible_list = bibles.list()

        found = False
        for bible in bible_list:
            if bible.name == 'De Heilige Schrift, Petrus Canisiusvertaling, 1939':
                found = True

        self.assertTrue(found)
