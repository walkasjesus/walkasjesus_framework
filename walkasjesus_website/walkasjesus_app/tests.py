from bible_lib import BibleBooks
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase

from walkasjesus_app.models import AbstractBibleReference, DirectBibleReference, Commandment
from walkasjesus_app.models import PrimaryBibleReference, BibleBooks
from walkasjesus_app.models.bibles import BibleTranslationMetaData, BibleTranslation
from walkasjesus_app.context_processors import cache_settings
from walkasjesus_app.views.detail_view import _allowed_target_audiences, _filter_grouped_media_by_audience


class BibleTranslationTestCase(TestCase):
    # Checking the exact number is not working because it can change over time.
    # This just gives an indication.
    approximate_bible_count = 100

    def test_all(self):
        all_bibles = BibleTranslation().all()
        self.assertGreaterEqual(len(all_bibles), self.approximate_bible_count)

    def test_all_in_supported_languages(self):
        all_bibles = len(BibleTranslation().all())
        all_in_supported_languages = len(BibleTranslation().all_in_supported_languages())
        self.assertGreater(all_in_supported_languages, 10)
        self.assertLess(all_in_supported_languages, all_bibles)

    def test_all_enabled_with_no_explicit_disabled_ones(self):
        all_bibles = len(BibleTranslation().all())
        all_enabled = len(BibleTranslation().all_enabled())
        self.assertEqual(all_enabled, all_bibles)

    def test_all_enabled_with_disabled_one(self):
        all_bibles = len(BibleTranslation().all())
        self.assertGreaterEqual(all_bibles, self.approximate_bible_count)
        self._disable('de4e12af7f28f599-01')
        all_enabled = len(BibleTranslation().all_enabled())
        self.assertEqual(all_enabled, all_bibles-1)

    def test_all_disabled(self):
        before_count = len(BibleTranslation().all_disabled())
        self._disable('de4e12af7f28f599-01')
        after_count = len(BibleTranslation().all_disabled())
        self.assertEqual(before_count+1, after_count)

    def _disable(self, bible_id: str):
        meta_data = BibleTranslationMetaData()
        meta_data.is_enabled = False
        meta_data.bible_id = bible_id
        meta_data.save()


class TestBibleReference(TestCase):
    def test_str(self):
        """ Test the to string method works """
        reference = DirectBibleReference()
        reference.book = BibleBooks.Daniel.name
        reference.begin_chapter = 2
        reference.begin_verse = 15

        self.assertEqual('Daniel 2:15', str(reference))


class UniqueModelConstraintsTestCase(TestCase):
    def setUp(self):
        Commandment.objects.create(id=1)

    def test_single_primary_bible_reference(self):
        """ Test to see that we can only have one primary reference """
        reference1 = PrimaryBibleReference(commandment_id=1)
        reference2 = PrimaryBibleReference(commandment_id=1)

        reference1.save()
        with self.assertRaises(IntegrityError):
            reference2.save()

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


class KidsModeMediaFilterTestCase(SimpleTestCase):
    def test_kids_mode_keeps_only_audience_neutral_media(self):
        grouped = {
            'superbook': [
                {'target_audience': 'kids', 'title': 'Kids only'},
                {'target_audience': 'adults', 'title': 'Adults only'},
                {'target_audience': 'any', 'title': 'Everyone'},
            ]
        }

        filtered = _filter_grouped_media_by_audience(grouped, {'any'})

        self.assertEqual(
            [item['title'] for item in filtered['superbook']],
            ['Everyone'],
        )

    def test_default_mode_keeps_adults_and_any_media(self):
        grouped = {
            'shortmovie': [
                {'target_audience': 'kids', 'title': 'Kids only'},
                {'target_audience': 'adults', 'title': 'Adults only'},
                {'target_audience': 'any', 'title': 'Everyone'},
            ]
        }

        filtered = _filter_grouped_media_by_audience(grouped, {'adults', 'any'})

        self.assertEqual(
            [item['title'] for item in filtered['shortmovie']],
            ['Adults only', 'Everyone'],
        )


class KidsModeCacheSettingsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_cache_settings_include_default_mode_key(self):
        request = self.factory.get('/')
        request.session = self.client.session

        self.assertEqual(cache_settings(request)['cache_on_kids_mode'], 'default')
        self.assertEqual(_allowed_target_audiences(request), {'any', 'adults'})

    def test_cache_settings_include_kids_mode_key(self):
        request = self.factory.get('/', HTTP_COOKIE='jc_kids_mode=true')
        request.session = self.client.session
        request.COOKIES['jc_kids_mode'] = 'true'

        self.assertEqual(cache_settings(request)['cache_on_kids_mode'], 'kids')
        self.assertEqual(_allowed_target_audiences(request), {'any'})
