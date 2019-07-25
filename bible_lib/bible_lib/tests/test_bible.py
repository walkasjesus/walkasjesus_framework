from unittest import TestCase
from unittest.mock import Mock

from bible import Bible
from bible_books import BibleBooks
from tests.dummy_responses import DummyResponses


class TestBible(TestCase):
    def test_get_book_id(self):
        self.assertEqual('GEN', Bible()._get_book_id(BibleBooks.Genesis))
        self.assertEqual('ISA', Bible()._get_book_id(BibleBooks.Isaiah))
        self.assertEqual('JON', Bible()._get_book_id(BibleBooks.Jonah))

    def test_get_verse(self):
        bible = Bible(bible_id='ead7b4cc5007389c-01')
        bible.client.get = Mock(return_value=DummyResponses().verses())
        verse = bible.verse(BibleBooks.John, 2, 4)
        self.assertIn('De magiërs gaven den koning ten antwoord: De koning leve voor eeuwig! Verhaal de droom aan uw '
                      'dienaars, dan zullen wij er de uitleg van geven.',
                      verse)
