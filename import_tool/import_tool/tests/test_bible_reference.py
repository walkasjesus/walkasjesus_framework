from unittest import TestCase, skip

from bible_lib import BibleBooks

from import_tool.bible_reference import BibleReference


class TestBibleReference(TestCase):
    def test_create_from_string_span_verse(self):
        ref = BibleReference().create_from_string('Ps 42:12-13')

        self.assertEqual(BibleBooks.Psalms, ref.book)
        self.assertEqual(42, ref.start_chapter)
        self.assertEqual(12, ref.start_verse)
        self.assertEqual(42, ref.end_chapter)
        self.assertEqual(13, ref.end_verse)

    def test_create_from_string_book_with_number(self):
        ref = BibleReference().create_from_string('1 Joh 2:3')

        self.assertEqual(BibleBooks.JohnFirstBook, ref.book)
        self.assertEqual(2, ref.start_chapter)
        self.assertEqual(3, ref.start_verse)
        self.assertEqual(2, ref.end_chapter)
        self.assertEqual(3, ref.end_verse)

    def test_create_from_string_simple(self):
        ref = BibleReference().create_from_string('Gen 1:2')

        self.assertEqual(BibleBooks.Genesis, ref.book)
        self.assertEqual(1, ref.start_chapter)
        self.assertEqual(2, ref.start_verse)
        self.assertEqual(1, ref.end_chapter)
        self.assertEqual(2, ref.end_verse)

    def test_create_from_string_multiple_chapters(self):
        ref = BibleReference().create_from_string('2 Jon 3:4-5:6')

        self.assertEqual(BibleBooks.JohnSecondBook, ref.book)
        self.assertEqual(3, ref.start_chapter)
        self.assertEqual(4, ref.start_verse)
        self.assertEqual(5, ref.end_chapter)
        self.assertEqual(6, ref.end_verse)
