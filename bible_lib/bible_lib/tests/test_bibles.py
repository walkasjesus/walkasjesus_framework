from unittest import TestCase
from unittest.mock import Mock

from bibles import Bibles
from tests.dummy_responses import DummyResponses


class TestBibles(TestCase):
    def test_list_bibles(self):
        bibles = Bibles()
        bibles.client.get = Mock(return_value=DummyResponses().bibles())
        bible_list = bibles.list()

        found = False
        for bible in bible_list:
            if bible.name == 'De Heilige Schrift, Petrus Canisiusvertaling, 1939':
                found = True

        self.assertTrue(found)

    def test_list_bibles_corrupt_data(self):
        bibles = Bibles()
        bibles.client.get = Mock(return_value='something unparsable')

        # We just want an empty list, no need to crash here.
        self.assertEqual([], bibles.list())

