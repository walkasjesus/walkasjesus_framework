from collections import Counter
from unittest import TestCase
from unittest.mock import Mock

from bible_lib.bible_api.api_bibles import ApiBibles
from bible_lib.tests.dummy_responses import DummyResponses


class TestBibles(TestCase):
    def test_list(self):
        bibles = ApiBibles()
        bibles.client.get = Mock(return_value=DummyResponses().bibles())
        bible_list = bibles.list()

        found = False
        for bible in bible_list:
            if bible.name == 'De Heilige Schrift, Petrus Canisiusvertaling, 1939':
                found = True

        self.assertTrue(found)

    def test_unique_names(self):
        bibles = ApiBibles()
        bibles.client.get = Mock(return_value=DummyResponses().bibles())
        bible_list = bibles.list()

        counted_names = Counter([b.name for b in bible_list])

        for name, count in counted_names.items():
            self.assertEqual(1, count, f'{name} has not an unique name')

    def test_dictionary(self):
        bibles = ApiBibles()
        bibles.client.get = Mock(return_value=DummyResponses().bibles())

        bible = bibles.dictionary()['ead7b4cc5007389c-01']
        self.assertEqual(bible.language, 'nl')
        self.assertEqual(bible.name, 'De Heilige Schrift, Petrus Canisiusvertaling, 1939')

    def test_list_bibles_corrupt_data(self):
        bibles = ApiBibles()
        bibles.client.get = Mock(return_value='something unparsable')

        # We just want an empty list, no need to crash here.
        self.assertEqual([], bibles.list())

