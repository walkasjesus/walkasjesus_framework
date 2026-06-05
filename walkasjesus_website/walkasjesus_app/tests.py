import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bible_lib import BibleBooks
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import translation

from walkasjesus_app.models import AbstractBibleReference, DirectBibleReference, Commandment, Lesson, LawOfMessiahDrawing
from walkasjesus_app.models import PrimaryBibleReference, BibleBooks
from walkasjesus_app.models.bibles import BibleTranslationMetaData, BibleTranslation
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

    @override_settings(SCRIPTURA_DISABLED_COMMENTATORS=['matthew-henry'])
    def test_cache_settings_include_scriptura_disabled_commentators(self):
        request = self.factory.get('/')
        request.session = self.client.session

        self.assertEqual(cache_settings(request)['scriptura_disabled_commentators'], 'matthew-henry')

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

        with self.settings(SCRIPTURA_DISABLED_COMMENTATORS=['matthew-henry']):
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
