from unittest import TestCase
from unittest.mock import Mock

from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_books import BibleBooks
from bible_lib.tests.dummy_responses import DummyResponses


class TestBible(TestCase):
    def test_get_verse(self):
        bible = ApiBible(bible_id='ead7b4cc5007389c-01')
        bible.client.get = Mock(return_value=DummyResponses().verses())
        verse = bible.verse(BibleBooks.John, 1, 51)

        bible.client.get.assert_called_with(
            'https://api.scripture.api.bible/v1/bibles/ead7b4cc5007389c-01/passages/JHN.1.51-JHN.1.51?content-type=text')
        self.assertIn('En Hij sprak tot hem: Voorwaar, voorwaar, Ik zeg u:', verse)

    def test_get_verses_spanning_multiple_chapters(self):
        bible = ApiBible(bible_id='ead7b4cc5007389c-01')
        bible.client.get = Mock(return_value=DummyResponses().verses())
        verses = bible.verses(BibleBooks.John, 1, 51, 2, 1)

        bible.client.get.assert_called_with(
            'https://api.scripture.api.bible/v1/bibles/ead7b4cc5007389c-01/passages/JHN.1.51-JHN.2.1?content-type=text')
        # Part of verse 51
        self.assertIn('En Hij sprak tot hem: Voorwaar, voorwaar, Ik zeg u:', verses)
        # Part of verse 1
        self.assertIn('En de derde dag werd er een bruiloft gevierd te Kana van Galilea', verses)
