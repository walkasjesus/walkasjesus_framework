from unittest import TestCase

from bible_lib import BibleBooks

from import_tool.bible_reference import BibleReference


class TestBibleReference(TestCase):
    def test_create_from_string(self):
        ref = BibleReference().create_from_string('Ps 42:2-3')
        self.assertEqual(BibleBooks.Psalms, ref.book)
        self.assertEqual(42, ref.start_chapter)
        self.assertEqual(2, ref.start_verse)
        self.assertEqual(42, ref.end_chapter)
        self.assertEqual(3, ref.end_verse)
