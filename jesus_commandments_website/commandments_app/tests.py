from django.db import IntegrityError
from django.test import TestCase

from bible_lib import BibleBooks
from commandments_app.models import AbstractBibleReference, DirectBibleReference, Commandment
from commandments_app.models import PrimaryBibleReference, BibleBooks


class TestBibleReference(TestCase):
    def test_str(self):
        """ Test the to string method works """
        reference = AbstractBibleReference()
        reference.book = BibleBooks.Daniel.name
        reference.begin_chapter = 2
        reference.begin_verse = 15

        self.assertEqual('Daniel 2:15', str(reference))


class UniqueModelConstraintsTestCase(TestCase):
    def setUp(self):
        Commandment.objects.get(id=1)

    def test_single_primary_bible_reference(self):
        """ Test to see that we can only have on primary reference """
        reference1 = PrimaryBibleReference(commandment_id=1)
        reference2 = PrimaryBibleReference(commandment_id=1)

        reference1.save()
        self.assertRaises(IntegrityError, reference2.save)

    def test_unique_direct_bible_references(self):
        """ Test to see if the unique constraint works"""
        reference1 = self.create_bible_reference(1, 1)
        reference2 = self.create_bible_reference(1, 2)

        reference1.save()

        self.assertIsNotNone(reference1.id)
        self.assertIsNone(reference2.id)

    def test_different_direct_bible_references(self):
        """ Test with the inverse of the unique test to see if the tests work at all. """
        reference1 = self.create_bible_reference(1, 1)
        reference2 = self.create_bible_reference(1, 2)

        reference1.save()
        reference2.save()

        self.assertIsNotNone(reference1.id)
        self.assertIsNotNone(reference2.id)

    def create_bible_reference(self, chapter, verse):
        bible_ref = DirectBibleReference(commandment_id=1)
        bible_ref.book = BibleBooks.John
        bible_ref.start_chapter = chapter
        bible_ref.start_verse = verse
        bible_ref.end_chapter = chapter
        bible_ref.end_verse = verse
        return bible_ref
