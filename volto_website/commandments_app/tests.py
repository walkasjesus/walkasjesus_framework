from django.test import TestCase

from bible_lib import BibleBooks
from commandments_app.models import AbstractBibleReference


class TestBibleReference(TestCase):
    def test_str(self):
        reference = AbstractBibleReference()
        reference.book = BibleBooks.Daniel.name
        reference.chapter = 2
        reference.verse = 15

        self.assertEqual('Daniel 2:15', str(reference))