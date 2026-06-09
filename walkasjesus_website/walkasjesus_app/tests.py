import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bible_lib import BibleBooks
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from walkasjesus_app.models import AbstractBibleReference, DirectBibleReference, Commandment, Lesson, LawOfMessiahDrawing
from walkasjesus_app.models import PrimaryBibleReference, BibleBooks
from walkasjesus_app.models.bibles import BibleTranslationMetaData, BibleTranslation
from walkasjesus_app.models.sword_commentary import SwordCommentaryEntry, SwordCommentarySource
from walkasjesus_app.lib.strongs_service import original_text_payload
from walkasjesus_app.context_processors import cache_settings
from walkasjesus_app.views.detail_view import (
    _allowed_media_languages,
    _allowed_target_audiences,
    _collect_shared_media_by_type,
    _filter_grouped_media_by_audience,
    _lesson_allowed_target_audiences,
)
from walkasjesus_app.views.user_preferences import ScripturaCommentaryProxyView, _append_unique_commentary
from walkasjesus_app.views.user_preferences import BibleTranslationsForLanguageView


class MockBibleStudyBible:
    def __init__(self, bible_id, name, language, verses_by_ref, copyright=''):
        self.id = bible_id
        self.name = name
        self.language = language
        self.copyright = copyright
        self._verses_by_ref = verses_by_ref

    def verses(self, book, start_chapter, start_verse, end_chapter, end_verse):
        return self._verses_by_ref.get((book.name, start_chapter, start_verse), '')


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
    def test_kids_mode_keeps_kids_and_audience_neutral_media(self):
        grouped = {
            'superbook': [
                {'target_audience': 'kids', 'title': 'Kids only'},
                {'target_audience': 'adults', 'title': 'Adults only'},
                {'target_audience': 'any', 'title': 'Everyone'},
            ]
        }

        filtered = _filter_grouped_media_by_audience(grouped, {'any', 'kids'})

        self.assertEqual(
            [item['title'] for item in filtered['superbook']],
            ['Kids only', 'Everyone'],
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

    def test_filter_respects_language_policy(self):
        grouped = {
            'song': [
                {'language': 'en', 'target_audience': 'any', 'title': 'English'},
                {'language': 'nl', 'target_audience': 'any', 'title': 'Dutch'},
                {'language': 'any', 'target_audience': 'any', 'title': 'Language independent'},
            ]
        }

        filtered = _filter_grouped_media_by_audience(grouped, {'any', 'adults'}, {'any', 'unknown', 'en'})

        self.assertEqual(
            [item['title'] for item in filtered['song']],
            ['English', 'Language independent'],
        )


class KidsModeCacheSettingsTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_cache_settings_include_default_mode_key(self):
        request = self.factory.get('/')
        request.session = self.client.session

        self.assertEqual(cache_settings(request)['cache_on_kids_mode'], 'default')
        self.assertEqual(_allowed_target_audiences(request), {'any', 'kids', 'adults'})

    def test_cache_settings_include_kids_mode_key(self):
        request = self.factory.get('/', HTTP_COOKIE='jc_kids_mode=true')
        request.session = self.client.session
        request.COOKIES['jc_kids_mode'] = 'true'

        self.assertEqual(cache_settings(request)['cache_on_kids_mode'], 'kids')
        self.assertEqual(_allowed_target_audiences(request), {'any', 'kids', 'adults'})

    def test_lesson_mode_always_uses_kids_and_any(self):
        self.assertEqual(_lesson_allowed_target_audiences(), {'any', 'kids'})

    @override_settings(DAVID_STERN_COMMENTARY_FOOTER_TEXT='Custom Stern footer')
    def test_cache_settings_include_david_stern_footer(self):
        request = self.factory.get('/')
        request.session = self.client.session

        self.assertEqual(cache_settings(request)['david_stern_commentary_footer_text'], 'Custom Stern footer')

    @override_settings(COMMENTARY_DISABLED_SOURCES=['matthew-henry'], DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=False, CJB_BIBLE_ENABLED=True)
    def test_cache_settings_include_scriptura_disabled_commentators(self):
        request = self.factory.get('/')
        request.session = self.client.session

        self.assertEqual(cache_settings(request)['scriptura_disabled_commentators'], 'matthew-henry')

    def test_cache_settings_include_sword_commentator_metadata_for_active_language(self):
        SwordCommentarySource.objects.create(
            source_id='sword-kingcomments-en',
            module_name='KingComments',
            display_name='King',
            language='en',
            is_enabled=True,
            copyright_text='Copyrighted; Free non-commercial distribution',
        )
        request = self.factory.get('/')
        request.session = self.client.session

        with translation.override('en'):
            payload = cache_settings(request)

        commentators = json.loads(payload['sword_commentators_json'])
        self.assertEqual(len(commentators), 1)
        self.assertEqual(commentators[0]['id'], 'sword-kingcomments-en')
        self.assertTrue(commentators[0]['auto_translate'])
        self.assertEqual(commentators[0]['native_language'], 'en')
        self.assertTrue(payload['sword_commentary_enabled'])
    @override_settings(SWORD_COMMENTARY_IMPORT_SOURCES=[
        {
            'id': 'sword-lightfoot-en',
            'enabled': True,
            'native_language': 'en',
            'auto_translate': True,
        }
    ])
    def test_cache_settings_include_auto_translated_lightfoot_for_dutch_ui(self):
        SwordCommentarySource.objects.create(
            source_id='sword-lightfoot-en',
            module_name='Lightfoot',
            display_name='John Lightfoot',
            language='en',
            is_enabled=True,
            copyright_text='Public Domain',
        )
        request = self.factory.get('/')
        request.session = self.client.session

        with translation.override('nl'):
            payload = cache_settings(request)

        commentators = json.loads(payload['sword_commentators_json'])
        self.assertEqual(len(commentators), 1)
        self.assertEqual(commentators[0]['id'], 'sword-lightfoot-en')
        self.assertTrue(commentators[0]['auto_translate'])
        self.assertEqual(commentators[0]['native_language'], 'en')

    @override_settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=True)
    def test_cache_settings_hide_david_stern_for_anonymous_when_login_required(self):
        request = self.factory.get('/')
        request.session = self.client.session
        request.user = AnonymousUser()

        self.assertFalse(cache_settings(request)['david_stern_commentary_available'])


class MediaLanguagePolicyTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_english_ui_uses_english_media_only(self):
        with translation.override('en'):
            request = self.factory.get('/')
            self.assertEqual(_allowed_media_languages(request), {'any', 'unknown', 'en'})

    def test_dutch_ui_uses_dutch_and_english_media(self):
        with translation.override('nl'):
            request = self.factory.get('/')
            self.assertEqual(_allowed_media_languages(request), {'any', 'unknown', 'nl', 'en'})


class StrongsServiceFallbackTestCase(TestCase):
    def test_original_text_payload_uses_non_clickable_fallback_for_missing_stepbible_rows(self):
        payload = original_text_payload('Psalms', 3, 2)

        self.assertGreater(len(payload['words']), 0)
        self.assertTrue(all(not word['clickable'] for word in payload['words']))
        self.assertTrue(all(not word['has_candidates'] for word in payload['words']))
        self.assertTrue(all(not word['detail_note'] for word in payload['words']))


class DynamicUiRegressionTestCase(TestCase):
    def test_base_modal_no_longer_renders_save_changes_button(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Save changes')

    def test_base_modal_defers_auto_apply_binding_until_dom_ready(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        # Function is defined in modal.html and called from base.html after jQuery loads
        self.assertContains(response, 'window.jcInitChangeLanguageModal')
        self.assertContains(response, 'jcInitChangeLanguageModal()')
        self.assertContains(response, 'changed.bs.select.jcAutoApply')

    def test_law_of_messiah_listing_no_longer_renders_apply_filter_button(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Apply Filter')

    def test_law_of_messiah_listing_defers_filter_auto_apply_binding_until_dom_ready(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        # Filter script is in extra_body_scripts (after jQuery), not block content
        self.assertContains(response, 'changed.bs.select.jcLawFilterAutoApply')
        # No DOMContentLoaded guard needed since script is after jQuery
        self.assertNotContains(response, 'initLawOfMessiahFilterAutoApply')


class SharedMediaDeduplicationTestCase(TestCase):
    def setUp(self):
        self.commandment = Commandment.objects.create(
            id=1001,
            title='Step 1001',
            title_negative='Step 1001 negative',
        )
        self.lesson = Lesson.objects.create(
            id=1001,
            title='Lesson 1001',
            commandment=self.commandment,
        )

    def test_collect_shared_media_deduplicates_by_content(self):
        common = {
            'media_type': LawOfMessiahDrawing.MEDIA_TYPE_SONG,
            'title': 'Create in me a clean heart',
            'author': 'Keith Green',
            'url': 'https://example.org/song',
            'target_audience': 'any',
            'language': 'en',
            'is_public': True,
        }
        LawOfMessiahDrawing.objects.create(commandment=self.commandment, **common)
        LawOfMessiahDrawing.objects.create(lesson=self.lesson, **common)

        grouped = _collect_shared_media_by_type(commandment=self.commandment, lesson=self.lesson)
        songs = grouped[LawOfMessiahDrawing.MEDIA_TYPE_SONG]

        self.assertEqual(len(songs), 1)
        self.assertEqual(songs[0].title, 'Create in me a clean heart')


class CommentaryProxyViewTestCase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_missing_required_params_returns_400(self):
        request = self.factory.get('/commentary-scriptura/', {'book': 'John'})
        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', json.loads(response.content.decode('utf-8')))

    def test_append_unique_commentary_deduplicates_sections(self):
        merged = _append_unique_commentary('Line one\n\nLine two', 'Line two\n\nLine three')

        self.assertEqual(merged, 'Line one\n\nLine two\n\nLine three')

    def test_append_unique_commentary_deduplicates_repeated_paragraphs_in_single_text(self):
        merged = _append_unique_commentary('', 'Fast. See Lk 18:12N.\n\nFast. See Lk 18:12N.')

        self.assertEqual(merged, 'Fast. See Lk 18:12N.')

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    @override_settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=False)
    def test_local_david_stern_source_uses_embedded_jnt_data(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {
                'source': 'david-stern',
                'book': 'Matthew',
                'chapter': '1',
            },
        )

        response = ScripturaCommentaryProxyView.as_view()(request)
        payload = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('18', payload)
        self.assertIn('Ruach HaKodesh', payload['18'])
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    @override_settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=False)
    def test_local_david_stern_source_returns_empty_for_missing_chapter(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {
                'source': 'david-stern',
                'book': 'Matthew',
                'chapter': '999',
            },
        )

        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode('utf-8')), {})
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    @override_settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=False)
    def test_local_david_stern_source_returns_verse_entries_not_intro_only(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {
                'source': 'david-stern',
                'book': 'Matthew',
                'chapter': '5',
            },
        )

        response = ScripturaCommentaryProxyView.as_view()(request)
        payload = json.loads(response.content.decode('utf-8'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('3', payload)
        self.assertTrue(str(payload['3']).strip())
        self.assertNotIn('\n\n\n', payload['3'])
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_proxy_calls_configured_bijbelapi_endpoint(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'16': 'For God so loved the world'}
        mock_get.return_value = mock_response

        request = self.factory.get(
            '/commentary-scriptura/',
            {
                'source': 'matthew-henry',
                'book': 'John',
                'chapter': '3',
                'verse': '16',
            },
        )

        with self.settings(
            COMMENTARY_API_URL='https://www.bijbelapi.com/api/commentary',
            BIJBEL_API_KEY='test-key',
        ):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode('utf-8')), {'16': 'For God so loved the world'})
        mock_get.assert_called_once_with(
            'https://www.bijbelapi.com/api/commentary',
            params={
                'source': 'matthew-henry',
                'book': 'John',
                'chapter': '3',
                'verse': '16',
            },
            headers={'x-api-key': 'test-key'},
            timeout=20,
        )

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_proxy_returns_404_for_disabled_commentator(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'matthew-henry', 'book': 'John', 'chapter': '3'},
        )

        with self.settings(COMMENTARY_DISABLED_SOURCES=['matthew-henry']):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn('error', json.loads(response.content.decode('utf-8')))
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_proxy_returns_403_for_david_stern_when_login_required_and_anonymous(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'david-stern', 'book': 'John', 'chapter': '3'},
        )
        request.user = AnonymousUser()

        with self.settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=True):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertIn('error', json.loads(response.content.decode('utf-8')))
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_proxy_allows_david_stern_when_login_required_and_authenticated(self, mock_get):
        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'david-stern', 'book': 'Matthew', 'chapter': '1'},
        )
        request.user = SimpleNamespace(is_authenticated=True)

        with self.settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=True):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertIn('18', payload)
        mock_get.assert_not_called()

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_proxy_omits_api_key_header_when_not_configured(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'0': 'intro'}
        mock_get.return_value = mock_response

        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'matthew-henry', 'book': 'John', 'chapter': '3'},
        )

        with self.settings(BIJBEL_API_KEY=''):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        mock_get.assert_called_once()
        self.assertEqual(mock_get.call_args.kwargs['headers'], {})

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_upstream_error_returns_502(self, mock_get):
        mock_get.side_effect = Exception('upstream failed')

        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'matthew-henry', 'book': 'John', 'chapter': '3'},
        )

        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 502)
        self.assertIn('error', json.loads(response.content.decode('utf-8')))


class SwordCommentaryProxyViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.source = SwordCommentarySource.objects.create(
            source_id='sword-kingcomments-en',
            module_name='KingComments',
            display_name='King',
            language='en',
            is_enabled=True,
            copyright_text='Copyrighted; Free non-commercial distribution',
        )
        SwordCommentaryEntry.objects.create(
            source=self.source,
            book='Genesis',
            book_key='genesis',
            chapter=1,
            verse=1,
            text='In the beginning commentary',
        )

    def test_proxy_returns_local_sword_commentary_entries(self):
        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'sword-kingcomments-en', 'book': 'Genesis', 'chapter': '1'},
        )

        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode('utf-8')), {'1': 'In the beginning commentary'})

    def test_proxy_returns_404_for_disabled_sword_source(self):
        request = self.factory.get(
            '/commentary-scriptura/',
            {'source': 'sword-kingcomments-en', 'book': 'Genesis', 'chapter': '1'},
        )

        with self.settings(COMMENTARY_DISABLED_SOURCES=['sword-kingcomments-en']):
            response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 404)
        self.assertIn('error', json.loads(response.content.decode('utf-8')))


class BibleTranslationsForLanguageViewTestCase(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('walkasjesus_app.views.user_preferences.BibleTranslation')
    def test_hides_cjb_for_anonymous_when_login_required(self, mock_bible_translation):
        mock_bible_translation.return_value.all_enabled.return_value = [
            SimpleNamespace(id='de4e12af7f28f599-01', name='KJV', language='en'),
            SimpleNamespace(id='jnt-stern-en', name='Complete Jewish Bible (David H. Stern, NT)', language='en'),
        ]

        request = self.factory.get('/bible-translations/?language=en')
        request.user = AnonymousUser()

        with self.settings(
            DEFAULT_BIBLE_ANY_LANGUAGE='de4e12af7f28f599-01',
            DEFAULT_BIBLE_PER_LANGUAGE={'en': 'jnt-stern-en'},
            CJB_BIBLE_ID='jnt-stern-en',
            CJB_BIBLE_ENABLED=True,
            CJB_BIBLE_LOGGED_IN_ONLY=True,
            DISABLED_BIBLE_TRANSLATIONS=[],
        ):
            response = BibleTranslationsForLanguageView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        returned_ids = [entry['id'] for entry in payload['bibles']]
        self.assertEqual(returned_ids, ['de4e12af7f28f599-01'])
        self.assertEqual(payload['default_bible_id'], 'de4e12af7f28f599-01')

    @patch('walkasjesus_app.views.user_preferences.BibleTranslation')
    def test_hides_cjb_for_authenticated_without_permission_when_login_required(self, mock_bible_translation):
        mock_bible_translation.return_value.all_enabled.return_value = [
            SimpleNamespace(id='de4e12af7f28f599-01', name='KJV', language='en'),
            SimpleNamespace(id='jnt-stern-en', name='Complete Jewish Bible (David H. Stern, NT)', language='en'),
        ]

        request = self.factory.get('/bible-translations/?language=en')
        request.user = SimpleNamespace(is_authenticated=True, has_perm=lambda perm: False)

        with self.settings(
            DEFAULT_BIBLE_ANY_LANGUAGE='de4e12af7f28f599-01',
            DEFAULT_BIBLE_PER_LANGUAGE={'en': 'jnt-stern-en'},
            CJB_BIBLE_ID='jnt-stern-en',
            CJB_BIBLE_ENABLED=True,
            CJB_BIBLE_LOGGED_IN_ONLY=True,
            DISABLED_BIBLE_TRANSLATIONS=[],
        ):
            response = BibleTranslationsForLanguageView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        returned_ids = [entry['id'] for entry in payload['bibles']]
        self.assertEqual(returned_ids, ['de4e12af7f28f599-01'])
        self.assertEqual(payload['default_bible_id'], 'de4e12af7f28f599-01')

    @patch('walkasjesus_app.views.user_preferences.BibleTranslation')
    def test_shows_cjb_for_authenticated_user_with_permission_when_login_required(self, mock_bible_translation):
        mock_bible_translation.return_value.all_enabled.return_value = [
            SimpleNamespace(id='de4e12af7f28f599-01', name='KJV', language='en'),
            SimpleNamespace(id='jnt-stern-en', name='Complete Jewish Bible (David H. Stern, NT)', language='en'),
        ]

        request = self.factory.get('/bible-translations/?language=en')
        request.user = SimpleNamespace(
            is_authenticated=True,
            has_perm=lambda perm: perm == 'walkasjesus_app.view_restricted_cjb_translation',
        )

        with self.settings(
            DEFAULT_BIBLE_ANY_LANGUAGE='de4e12af7f28f599-01',
            DEFAULT_BIBLE_PER_LANGUAGE={'en': 'jnt-stern-en'},
            CJB_BIBLE_ID='jnt-stern-en',
            CJB_BIBLE_ENABLED=True,
            CJB_BIBLE_LOGGED_IN_ONLY=True,
            DISABLED_BIBLE_TRANSLATIONS=[],
        ):
            response = BibleTranslationsForLanguageView.as_view()(request)

        payload = json.loads(response.content.decode('utf-8'))
        returned_ids = [entry['id'] for entry in payload['bibles']]
        self.assertEqual(returned_ids, ['de4e12af7f28f599-01', 'jnt-stern-en'])
        self.assertEqual(payload['default_bible_id'], 'jnt-stern-en')


class BibleStudyLanguageCoverageTestCase(SimpleTestCase):
    @patch('walkasjesus_app.views.user_preferences.BibleTranslation')
    def test_bible_translations_endpoint_returns_bibles_for_each_language(self, mock_bible_translation):
        mock_bible_translation.return_value.all_enabled.return_value = [
            SimpleNamespace(id='en-kjv', name='KJV', language='en'),
            SimpleNamespace(id='en-nkjv', name='NKJV', language='en'),
            SimpleNamespace(id='nl-hsv', name='HSV', language='nl'),
            SimpleNamespace(id='nl-svv', name='SVV', language='nl'),
        ]

        with self.settings(
            DEFAULT_BIBLE_ANY_LANGUAGE='en-kjv',
            DEFAULT_BIBLE_PER_LANGUAGE={'en': 'en-kjv', 'nl': 'nl-hsv'},
            DISABLED_BIBLE_TRANSLATIONS=[],
            CJB_BIBLE_ENABLED=False,
        ):
            cases = [
                ('en', ['en-kjv', 'en-nkjv'], 'en-kjv'),
                ('nl', ['nl-hsv', 'nl-svv'], 'nl-hsv'),
            ]
            for language_code, expected_ids, expected_default in cases:
                with self.subTest(language_code=language_code):
                    response = self.client.get(
                        reverse('commandments:bible_translations_for_language'),
                        {'language': language_code},
                    )
                    self.assertEqual(response.status_code, 200)
                    payload = json.loads(response.content.decode('utf-8'))
                    self.assertEqual([entry['id'] for entry in payload['bibles']], expected_ids)
                    self.assertEqual(payload['default_bible_id'], expected_default)

    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_bible_study_verses_endpoint_returns_texts_for_english_and_dutch_bibles(self, mock_bible_translation):
        english_bible = MockBibleStudyBible(
            'en-kjv',
            'KJV',
            'en',
            {
                ('John', 3, 16): 'For God so loved the world',
                ('John', 3, 17): 'For God sent not his Son into the world to condemn the world',
            },
        )
        dutch_bible = MockBibleStudyBible(
            'nl-hsv',
            'HSV',
            'nl',
            {
                ('Genesis', 1, 1): 'In het begin schiep God de hemel en de aarde.',
                ('Genesis', 1, 2): 'De aarde nu was woest en leeg.',
            },
        )
        bible_map = {
            english_bible.id: english_bible,
            dutch_bible.id: dutch_bible,
        }
        mock_bible_translation.return_value.get.side_effect = lambda bible_id: bible_map.get(bible_id)

        with self.settings(DISABLED_BIBLE_TRANSLATIONS=[], CJB_BIBLE_ENABLED=False):
            cases = [
                ('en-kjv', 'John', 3, 16, 17, {
                    '16': 'For God so loved the world',
                    '17': 'For God sent not his Son into the world to condemn the world',
                }),
                ('nl-hsv', 'Genesis', 1, 1, 2, {
                    '1': 'In het begin schiep God de hemel en de aarde.',
                    '2': 'De aarde nu was woest en leeg.',
                }),
            ]
            for bible_id, book, chapter, start_verse, end_verse, expected_verses in cases:
                with self.subTest(bible_id=bible_id, book=book):
                    response = self.client.post(
                        reverse('commandments:bible_study_verses'),
                        {
                            'bible_id': bible_id,
                            'book': book,
                            'chapter': chapter,
                            'start_verse': start_verse,
                            'end_verse': end_verse,
                        },
                    )
                    self.assertEqual(response.status_code, 200)
                    payload = json.loads(response.content.decode('utf-8'))
                    self.assertEqual(payload['verses'], expected_verses)


class CommentaryTranslationViewTestCase(SimpleTestCase):
    @patch('walkasjesus_app.views.user_preferences._translate_commentary_text')
    def test_translation_endpoint_machine_translates_commentary_text(self, mock_translate_commentary_text):
        cache.clear()
        mock_translate_commentary_text.return_value = 'In het begin'

        response = self.client.post(
            reverse('commandments:commentary_translate'),
            {'text': 'In the beginning', 'target_language': 'nl'},
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['translated_text'], 'In het begin')
        self.assertEqual(payload['language'], 'nl')
        self.assertTrue(payload['machine_translated'])
        mock_translate_commentary_text.assert_called_once_with('In the beginning', 'nl')


class CommentaryCoverageForGenesisTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.lightfoot = SwordCommentarySource.objects.create(
            source_id='sword-lightfoot-en',
            module_name='Lightfoot',
            display_name='John Lightfoot',
            language='en',
            is_enabled=True,
            copyright_text='Public Domain',
        )
        self.king_en = SwordCommentarySource.objects.create(
            source_id='sword-kingcomments-en',
            module_name='KingComments',
            display_name='King',
            language='en',
            is_enabled=True,
            copyright_text='Copyrighted; Free non-commercial distribution',
        )
        self.king_nl = SwordCommentarySource.objects.create(
            source_id='sword-kingcomments-nl',
            module_name='DutKingComments',
            display_name='King',
            language='nl',
            is_enabled=True,
            copyright_text='Copyrighted; Free non-commercial distribution',
        )
        self.dutkant = SwordCommentarySource.objects.create(
            source_id='sword-dutkant-nl',
            module_name='DutKant',
            display_name='Statenvertaling Kanttekeningen',
            language='nl',
            is_enabled=True,
            copyright_text='Public Domain',
        )

        entries = [
            (self.lightfoot, 'John Lightfoot on Genesis 1:1'),
            (self.king_en, 'King commentary on Genesis 1:1'),
            (self.king_nl, 'King commentaar op Genesis 1:1'),
            (self.dutkant, 'Kanttekening bij Genesis 1:1'),
        ]
        for source, text in entries:
            SwordCommentaryEntry.objects.create(
                source=source,
                book='Genesis',
                book_key='genesis',
                chapter=1,
                verse=1,
                text=text,
            )

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    def test_genesis_commentary_is_available_for_all_sources_except_david_stern(self, mock_get):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'1': 'Matthew Henry on Genesis 1:1'}
        mock_get.return_value = mock_response

        cases = [
            ('matthew-henry', 'Matthew Henry on Genesis 1:1'),
            ('sword-lightfoot-en', 'John Lightfoot on Genesis 1:1'),
            ('sword-kingcomments-en', 'King commentary on Genesis 1:1'),
            ('sword-kingcomments-nl', 'King commentaar op Genesis 1:1'),
            ('sword-dutkant-nl', 'Kanttekening bij Genesis 1:1'),
        ]

        for source_id, expected_text in cases:
            with self.subTest(source_id=source_id):
                request = self.factory.get(
                    reverse('commandments:commentary_scriptura'),
                    {'source': source_id, 'book': 'Genesis', 'chapter': '1', 'verse': '1'},
                )
                response = ScripturaCommentaryProxyView.as_view()(request)
                self.assertEqual(response.status_code, 200)
                payload = json.loads(response.content.decode('utf-8'))
                self.assertEqual(payload.get('1'), expected_text)

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    @override_settings(DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY=False)
    def test_genesis_commentary_handles_david_stern_as_separate_exception(self, mock_get):
        request = self.factory.get(
            reverse('commandments:commentary_scriptura'),
            {'source': 'david-stern', 'book': 'Genesis', 'chapter': '1', 'verse': '1'},
        )

        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode('utf-8')), {})
        mock_get.assert_not_called()

    def test_lightfoot_commentary_proxy_returns_original_text_for_frontend_translation(self):
        request = self.factory.get(
            reverse('commandments:commentary_scriptura'),
            {'source': 'sword-lightfoot-en', 'book': 'Genesis', 'chapter': '1', 'verse': '1'},
        )

        response = ScripturaCommentaryProxyView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload, {'1': 'John Lightfoot on Genesis 1:1'})
