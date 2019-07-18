from django.test import TestCase

from callings_app.lib.bible_books import BibleBooks
from callings_app.models import BibleReference


class TestBibleReference(TestCase):
    def test_str(self):
        reference = BibleReference()
        reference.book = BibleBooks.Daniel.name
        reference.chapter = 2
        reference.verse = 15

        self.assertEqual('Daniel 2:15', str(reference))
