import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.cache import cache
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.template.loader import get_template, render_to_string
from django.urls import reverse
from django.utils import translation

from walkasjesus_app.admin import MediaResourceAdmin
from walkasjesus_app.management.commands.import_media_lessons import Command as ImportLessonMediaCommand
from walkasjesus_app.models import AbstractBibleReference, DirectBibleReference, Commandment, Lesson, LawOfMessiah, LawOfMessiahDrawing
from walkasjesus_app.models import PrimaryBibleReference, BibleBooks
from walkasjesus_app.models.bibles import (
    BibleTranslationMetaData,
    BibleTranslation,
    LocalCompleteJewishBible,
    LocalStatenvertalingBible,
)
from walkasjesus_app.models.sword_commentary import SwordCommentaryEntry, SwordCommentarySource
from walkasjesus_app.models.bible_usage import BibleTranslationUsageDaily, PageVisitDaily
from walkasjesus_app.models.law_of_messiah_media import MediaResource
from walkasjesus_app.models.media_review import MediaReviewRequest
from walkasjesus_app.lib.bible_api_rate_limit import BibleApiRateLimitExceeded, consume_bible_api_quota
from walkasjesus_app.lib.strongs_service import (
    _candidate_payload,
    _step_reference_to_display,
    _stepbible_rows_for_verse,
    english_alignment_payload,
    localized_original_text_payload,
    original_text_payload,
)
from walkasjesus_app.context_processors import cache_settings
from walkasjesus_app.lib.media_cache_version import MEDIA_CACHE_VERSION_KEY, get_media_cache_version
from walkasjesus_app.templatetags.media_extras import is_youtube_url_filter, youtube_captions_url
from walkasjesus_app.views.admin.admin_bible_usage_view import AdminBibleUsageView
from walkasjesus_app.views.admin.admin_page_usage_view import AdminPageUsageView
from walkasjesus_app.views.detail_view import (
    _allowed_media_languages,
    _allowed_target_audiences,
    _collect_shared_media_by_type,
    _filter_grouped_media_by_audience,
    _lesson_allowed_target_audiences,
)
from walkasjesus_app.views.user_preferences import (
    ScripturaCommentaryProxyView,
    _append_unique_commentary,
    _translate_commentary_text,
)
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

    def _available_bible_id(self):
        disabled_ids = {
            str(item).strip()
            for item in getattr(settings, 'DISABLED_BIBLE_TRANSLATIONS', [])
            if str(item).strip()
        }
        disabled_ids.update(
            str(meta_data.bible_id).strip()
            for meta_data in BibleTranslationMetaData.objects.all()
            if str(meta_data.bible_id).strip()
        )

        for bible in BibleTranslation().all():
            bible_id = str(getattr(bible, 'id', '')).strip()
            if bible_id and bible_id not in disabled_ids:
                return bible_id

        self.fail('No non-disabled Bible translation available for this test.')

    def test_all(self):
        all_bibles = BibleTranslation().all()
        self.assertGreaterEqual(len(all_bibles), self.approximate_bible_count)

    def test_all_in_supported_languages(self):
        all_bibles = len(BibleTranslation().all())
        all_in_supported_languages = len(BibleTranslation().all_in_supported_languages())
        self.assertGreater(all_in_supported_languages, 10)
        self.assertLess(all_in_supported_languages, all_bibles)

    def test_all_in_supported_languages_excludes_database_disabled_bibles(self):
        with override_settings(DISABLED_BIBLE_TRANSLATIONS=[], FORCE_ENABLED_BIBLE_TRANSLATIONS=[]):
            target_bible = BibleTranslation().all_in_supported_languages()[0]
            self._disable(target_bible.id)
            supported_ids = {bible.id for bible in BibleTranslation().all_in_supported_languages()}

        self.assertNotIn(target_bible.id, supported_ids)

    def test_all_enabled_with_no_explicit_disabled_ones(self):
        with override_settings(DISABLED_BIBLE_TRANSLATIONS=[], FORCE_ENABLED_BIBLE_TRANSLATIONS=[]):
            all_bibles = len(BibleTranslation().all())
            all_enabled = len(BibleTranslation().all_enabled())
            self.assertEqual(all_enabled, all_bibles)

    def test_all_enabled_with_disabled_one(self):
        with override_settings(DISABLED_BIBLE_TRANSLATIONS=[], FORCE_ENABLED_BIBLE_TRANSLATIONS=[]):
            all_bibles = len(BibleTranslation().all())
            self.assertGreaterEqual(all_bibles, self.approximate_bible_count)
            target_id = self._available_bible_id()
            self._disable(target_id)
            all_enabled = len(BibleTranslation().all_enabled())
            self.assertEqual(all_enabled, all_bibles-1)

    @override_settings(DISABLED_BIBLE_TRANSLATIONS=['de4e12af7f28f599-01'])
    def test_all_enabled_respects_settings_disabled_ids(self):
        enabled_ids = {b.id for b in BibleTranslation().all_enabled()}
        self.assertNotIn('de4e12af7f28f599-01', enabled_ids)

    def test_all_disabled(self):
        with override_settings(DISABLED_BIBLE_TRANSLATIONS=[], FORCE_ENABLED_BIBLE_TRANSLATIONS=[]):
            before_count = len(BibleTranslation().all_disabled())
            target_id = self._available_bible_id()
            self._disable(target_id)
            after_count = len(BibleTranslation().all_disabled())
            self.assertEqual(before_count+1, after_count)

    def test_all_disabled_uses_loaded_bibles_without_rebuilding_factory(self):
        with override_settings(DISABLED_BIBLE_TRANSLATIONS=[], FORCE_ENABLED_BIBLE_TRANSLATIONS=[]):
            target_id = self._available_bible_id()
            self._disable(target_id)

            with patch.object(BibleTranslation._bible_factory, 'create', side_effect=AssertionError('factory create should not be called')):
                disabled_ids = {bible.id for bible in BibleTranslation().all_disabled()}

        self.assertIn(target_id, disabled_ids)

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
        self.assertEqual(_allowed_target_audiences(request), {'any', 'adults'})

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


class AdminUsageReportViewTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = self._create_staff_user()

    def _create_staff_user(self):
        return get_user_model().objects.create_user(username='admin-reports', email='admin@example.com', password='secret', is_staff=True, is_active=True)

    def _request(self, path='/?year=2024'):
        request = self.factory.get(path)
        request.user = self.user
        request.session = self.client.session
        return request

    def test_page_usage_view_includes_monthly_breakdown_and_chart(self):
        PageVisitDaily.objects.create(usage_date='2024-01-02', page_path='/home', page_label='Home', language_code='en', user_kind='authenticated', user_key='u1', visit_count=3)
        PageVisitDaily.objects.create(usage_date='2024-02-05', page_path='/home', page_label='Home', language_code='en', user_kind='anonymous', user_key='u2', visit_count=5)

        response = AdminPageUsageView.as_view()(self._request())
        content = response.content.decode('utf-8')
        self.assertIn('January', content)
        self.assertIn('February', content)
        self.assertIn('<svg', content)

    def test_bible_usage_view_includes_monthly_breakdown_and_chart(self):
        BibleTranslationUsageDaily.objects.create(usage_date='2024-01-03', bible_id='eng-1', bible_name='English', bible_language='en', source='api', endpoint='verses_api', user_kind='authenticated', user_key='u1', request_count=4, verse_count=10)
        BibleTranslationUsageDaily.objects.create(usage_date='2024-02-04', bible_id='eng-1', bible_name='English', bible_language='en', source='cache', endpoint='study_page', user_kind='anonymous', user_key='u2', request_count=6, verse_count=8)

        response = AdminBibleUsageView.as_view()(self._request())
        content = response.content.decode('utf-8')
        self.assertIn('January', content)
        self.assertIn('February', content)
        self.assertIn('<svg', content)


class BibleApiRateLimitTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def _request(self, remote_addr='203.0.113.10'):
        request = self.factory.get('/', REMOTE_ADDR=remote_addr, HTTP_USER_AGENT='rate-limit-test')
        request.user = AnonymousUser()
        request.session = self.client.session
        return request

    @override_settings(BIBLE_API_RATE_LIMIT_ENABLED=True, BIBLE_API_DAILY_CALL_LIMIT=1, BIBLE_API_RATE_LIMIT_WHITELIST=[])
    def test_rate_limit_blocks_and_records_usage(self):
        bible = SimpleNamespace(id='eng-1', name='English', language='en')
        request = self._request()

        consume_bible_api_quota(request, bible, BibleTranslationUsageDaily.ENDPOINT_VERSES_API)

        with self.assertRaises(BibleApiRateLimitExceeded):
            consume_bible_api_quota(request, bible, BibleTranslationUsageDaily.ENDPOINT_VERSES_API)

        blocked = BibleTranslationUsageDaily.objects.get(source=BibleTranslationUsageDaily.SOURCE_BLOCKED)
        self.assertEqual(blocked.bible_id, 'eng-1')
        self.assertEqual(blocked.endpoint, BibleTranslationUsageDaily.ENDPOINT_VERSES_API)
        self.assertEqual(blocked.request_count, 1)

    @override_settings(BIBLE_API_RATE_LIMIT_ENABLED=True, BIBLE_API_DAILY_CALL_LIMIT=1, BIBLE_API_RATE_LIMIT_WHITELIST=['10.80.80.0/24'])
    def test_rate_limit_skips_whitelisted_ip(self):
        bible = SimpleNamespace(id='eng-1', name='English', language='en')
        request = self._request(remote_addr='10.80.80.140')

        consume_bible_api_quota(request, bible, BibleTranslationUsageDaily.ENDPOINT_VERSES_API)
        consume_bible_api_quota(request, bible, BibleTranslationUsageDaily.ENDPOINT_VERSES_API)

        self.assertFalse(BibleTranslationUsageDaily.objects.filter(source=BibleTranslationUsageDaily.SOURCE_BLOCKED).exists())


class MediaReviewWorkflowTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.reviewer = get_user_model().objects.create_user(
            username='media-reviewer',
            email='reviewer@example.com',
            password='secret',
            is_staff=True,
            is_active=True,
        )
        self.reviewer.user_permissions.add(
            Permission.objects.get(codename='can_review_media_resources'),
            Permission.objects.get(codename='change_mediaresource'),
        )
        self.reviewer.save()
        self.applicant = get_user_model().objects.create_user(
            username='media-applicant',
            email='applicant@example.com',
            password='secret',
            is_staff=True,
            is_active=True,
        )

    def test_approval_sets_resource_public_and_sends_mail(self):
        resource = MediaResource.objects.create(
            title='New video',
            author='Test author',
            media_type='movie',
            description='A test media resource',
            is_public=False,
        )
        review_request = MediaReviewRequest.objects.create(resource=resource, applicant=self.applicant)

        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('admin:media_review_dashboard'),
            {'request_id': review_request.pk, 'action': 'approve', 'review_notes': 'Looks good'}
        )

        review_request.refresh_from_db()
        resource.refresh_from_db()
        self.assertEqual(review_request.status, 'approved')
        self.assertTrue(resource.is_public)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('approved', mail.outbox[0].subject.lower())

    def test_contributor_save_forces_private_and_creates_review_request(self):
        contributor = get_user_model().objects.create_user(
            username='media-contributor',
            email='contributor@example.com',
            password='secret',
            is_staff=True,
            is_active=True,
        )
        contributor.user_permissions.add(
            Permission.objects.get(codename='add_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='change_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_mediaresource', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_commandment', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_lesson', content_type__app_label='commandments_app'),
            Permission.objects.get(codename='view_lawofmessiah', content_type__app_label='commandments_app'),
        )
        contributor.save()

        request = self.factory.get('/')
        request.user = contributor
        request.session = self.client.session

        resource = MediaResource(title='Contributor video', author='Tester', media_type='movie', description='Needs review')
        admin_instance = MediaResourceAdmin(MediaResource, admin.site)
        admin_instance.save_model(request, resource, form=None, change=False)

        resource.refresh_from_db()
        self.assertFalse(resource.is_public)
        self.assertTrue(MediaReviewRequest.objects.filter(resource=resource, applicant=contributor, status='pending').exists())

    def test_approval_saves_reviewed_resource_fields(self):
        resource = MediaResource.objects.create(
            title='Needs editing',
            author='Original author',
            media_type='movie',
            description='Original description',
            is_public=False,
        )
        review_request = MediaReviewRequest.objects.create(resource=resource, applicant=self.applicant)

        self.client.force_login(self.reviewer)
        response = self.client.post(
            reverse('admin:media_review_dashboard'),
            {
                'request_id': review_request.pk,
                'action': 'approve',
                'review_notes': 'Looks good',
                'title': 'Edited title',
                'description': 'Edited description',
                'author': 'Updated author',
                'media_type': 'shortmovie',
                'language': 'en',
                'target_audience': 'adults',
            },
        )

        resource.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(resource.title, 'Edited title')
        self.assertEqual(resource.description, 'Edited description')
        self.assertEqual(resource.author, 'Updated author')
        self.assertEqual(resource.media_type, 'shortmovie')
        self.assertTrue(resource.is_public)


class EnglishWordAlignmentTestCase(TestCase):
    def _word_index_for(self, tokens, english_word):
        for token in tokens:
            if token['text'].lower() == english_word:
                return token['word_index']
        return None

    def test_hebrew_verse_aligns_kjv_words_to_original_tokens(self):
        payload = english_alignment_payload(
            'Exodus', 1, 1,
            'Now these are the names of the children of Israel, which came into Egypt; '
            'every man and his household came with Jacob.',
        )
        original = original_text_payload('Exodus', 1, 1)
        tokens = payload['tokens']

        self.assertGreater(payload['aligned_count'], 10)
        children_index = self._word_index_for(tokens, 'children')
        self.assertIsNotNone(children_index)
        self.assertIn('H1121', [
            candidate['strongs_number']
            for candidate in original['words'][children_index]['candidates']
        ])
        self.assertEqual(self._word_index_for(tokens, 'now'), -1)
        self.assertEqual(
            ''.join(token['text'] for token in tokens),
            'Now these are the names of the children of Israel, which came into Egypt; '
            'every man and his household came with Jacob.',
        )

    def test_greek_verse_aligns_kjv_words_to_original_tokens(self):
        payload = english_alignment_payload(
            'John', 3, 16,
            'For God so loved the world, that he gave his only begotten Son, that whosoever '
            'believeth in him should not perish, but have everlasting life.',
        )
        original = original_text_payload('John', 3, 16)

        self.assertGreater(payload['aligned_count'], 10)
        loved_index = self._word_index_for(payload['tokens'], 'loved')
        self.assertIsNotNone(loved_index)
        self.assertIn('G0025', [
            candidate['strongs_number']
            for candidate in original['words'][loved_index]['candidates']
        ])

    def test_tagged_kjv_source_uses_direct_strongs_lookup(self):
        payload = english_alignment_payload(
            'Genesis', 1, 1,
            'In the beginning God created the heaven and the earth.',
            tagged_source='kjv',
        )

        self.assertEqual(payload['method'], 'tagged')
        # The KJV reorders "God created" relative to the Hebrew, which only a tag lookup resolves.
        self.assertEqual(self._word_index_for(payload['tokens'], 'created'), 1)
        self.assertEqual(self._word_index_for(payload['tokens'], 'god'), 2)

    def test_unknown_tagged_source_falls_back_to_lexicon_alignment(self):
        payload = english_alignment_payload(
            'Genesis', 1, 1,
            'In the beginning God created the heaven and the earth.',
            tagged_source='does-not-exist',
        )

        self.assertEqual(payload['method'], 'lexicon')
        self.assertGreater(payload['aligned_count'], 5)

    def test_dutch_verse_uses_statenvertaling_tagging(self):
        payload = english_alignment_payload(
            'Genesis', 1, 1,
            'In het begin schiep God de hemel en de aarde.',
            tagged_source='svv',
            allow_scoring=False,
        )

        self.assertEqual(payload['method'], 'tagged')
        self.assertEqual(self._word_index_for(payload['tokens'], 'schiep'), 1)
        self.assertEqual(self._word_index_for(payload['tokens'], 'god'), 2)

    def test_untagged_non_english_verse_returns_no_alignment(self):
        payload = english_alignment_payload(
            'Genesis', 1, 1,
            'Am Anfang schuf Gott Himmel und Erde.',
            allow_scoring=False,
        )

        self.assertEqual(payload['aligned_count'], 0)
        self.assertEqual(payload['tokens'], [])


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'dutch-original-text-tests',
    },
})
class DutchOriginalTextTestCase(TestCase):
    @patch('walkasjesus_app.lib.strongs_service.original_text_payload')
    @patch('walkasjesus_app.lib.strongs_service.cache')
    def test_localized_cache_hit_does_not_load_original_payload(self, mocked_cache, original):
        mocked_cache.get.return_value = {'words': [{'text': 'cached'}]}
        result = localized_original_text_payload('Genesis', 1, 1, 'nl')
        self.assertEqual(result, {'words': [{'text': 'cached'}]})
        original.assert_not_called()

    @patch('walkasjesus_app.lib.strongs_service._tagged_usage_index', return_value={'H1': [['een', 3, ['Gen.1:1']]]})
    @patch('walkasjesus_app.lib.strongs_service._tagged_run_assignments', return_value=[])
    @patch('walkasjesus_app.lib.strongs_service._tagged_segments', return_value=[])
    @patch('walkasjesus_app.lib.strongs_service.cache')
    @patch('walkasjesus_app.lib.strongs_service.original_text_payload')
    def test_localization_does_not_mutate_original_payload(self, original, mocked_cache, segments, assignments, usage):
        import copy

        payload = {
            'words': [{
                'text': 'word', 'clickable': True, 'candidates': [{'strongs_number': 'H1'}],
                'word_components': [], 'grammar_details': [],
                'hebrew_letters': [{'name': 'Aleph', 'traditional_image': 'Ox'}],
            }],
        }
        before = copy.deepcopy(payload)
        original.return_value = payload
        mocked_cache.get.return_value = None
        localized = localized_original_text_payload('Genesis', 1, 1, 'nl')
        self.assertEqual(payload, before)
        self.assertEqual(localized['words'][0]['candidates'][0]['local_usage'][0]['label'], 'een')
        self.assertIn('name_local', localized['words'][0]['hebrew_letters'][0])

    def test_reference_set_preserves_reviewed_letter_roles(self):
        from walkasjesus_app.lib.strongs_service import _hebrew_letter_data

        reference_path = Path(settings.BASE_DIR) / 'walkasjesus_app/testdata/hebrew_segmentation_reference.json'
        reference = json.loads(reference_path.read_text(encoding='utf-8'))
        for case in reference['cases']:
            with self.subTest(reference=f"{case['book']} {case['chapter']}:{case['verse']}", word=case['prefix']):
                words = original_text_payload(case['book'], case['chapter'], case['verse'])['words']
                matches = [word for word in words if word['text'].startswith(case['prefix'])]
                self.assertEqual(len(matches), 1)
                expected = [
                    (letter['glyph'], role)
                    for role, text in case['parts'] for letter in _hebrew_letter_data(text)
                ]
                actual = [
                    (letter['glyph'], part['role'])
                    for part in matches[0]['word_components'] for letter in part['letters']
                ]
                self.assertEqual(actual, expected, msg=f"Source: {case['source']}")

    def test_incomplete_hebrew_analysis_is_reported_without_claiming_certainty(self):
        cases = (
            ('Hosea', 2, 3, 'וְשַׁתִּ', True),
            ('Deuteronomy', 4, 2, 'תֹסִ', False),
            ('Job', 1, 4, 'אַחְי', False),
            ('Ruth', 2, 12, 'כְּנָפָ', False),
            ('Psalms', 23, 1, 'אֶחְסָ', False),
            ('Genesis', 4, 22, 'נְחֹ', False),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse, word=start):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                self.assertEqual(word['hebrew_analysis_may_be_incomplete'], expected)

    def test_incomplete_analysis_handles_missing_data_and_partial_inflections(self):
        from walkasjesus_app.lib.strongs_service import (
            _fallback_token_payload,
            _hebrew_analysis_may_be_incomplete,
            _hebrew_letter_data,
            _parse_hebrew_word_components,
        )

        raw = '{H3789=כָּתַב=write}'
        surface = 'תִּכְתְּבו'
        parts = _parse_hebrew_word_components(raw, surface, 'HVqi2mp')
        self.assertTrue(_hebrew_analysis_may_be_incomplete(surface, 'HVqi2mp', parts))
        partial = [
            {'role': 'prefix', 'strongs_number': '', 'morphology_code': 'HVqi2mp',
             'letters': _hebrew_letter_data('תִּ')},
            {'role': 'root', 'strongs_number': 'H3789', 'letters': _hebrew_letter_data('כְתְּבוּ')},
        ]
        self.assertTrue(_hebrew_analysis_may_be_incomplete('תִּכְתְּבוּ', 'HVqi2mp', partial))
        self.assertTrue(_hebrew_analysis_may_be_incomplete('כָּתַב', 'HVqp3ms', []))
        untagged_grammar = _parse_hebrew_word_components(raw, 'כָּתַב', '')
        self.assertTrue(any(part['role'] == 'root' for part in untagged_grammar))
        self.assertTrue(_hebrew_analysis_may_be_incomplete('כָּתַב', '', untagged_grammar))
        self.assertFalse(_hebrew_analysis_may_be_incomplete('׃', '', []))
        self.assertTrue(_fallback_token_payload('כָּתַב', 'hebrew')['hebrew_analysis_may_be_incomplete'])
        self.assertFalse(_fallback_token_payload('λόγος', 'greek')['hebrew_analysis_may_be_incomplete'])

    @patch('walkasjesus_app.views.user_preferences._translate_google_batch', return_value=[])
    def test_incomplete_analysis_survives_localization(self, mock_translate):
        word = next(word for word in localized_original_text_payload('Hosea', 2, 3, 'nl')['words']
                    if word['text'].startswith('וְשַׁתִּ'))
        self.assertTrue(word['hebrew_analysis_may_be_incomplete'])
        root = next(part for part in word['word_components'] if part['role'] == 'root')
        self.assertEqual(root['analysis_origin'], 'stepbible')
        self.assertEqual(root['letters'][-1]['possible_overlap_role'], 'suffix')

    def test_possible_fused_ending_and_component_origins(self):
        word = next(word for word in original_text_payload('Hosea', 2, 3)['words']
                    if word['text'].startswith('וְשַׁתִּ'))
        components = word['word_components']
        self.assertEqual([part['analysis_origin'] for part in components], ['stepbible'] * 3)
        root = next(part for part in components if part['role'] == 'root')
        self.assertEqual([letter.get('possible_overlap_role') for letter in root['letters']], [None, 'suffix'])
        self.assertEqual(
            [letter['glyph'] for part in components for letter in part['letters']],
            [letter['glyph'] for letter in word['hebrew_letters']],
        )
        self.assertTrue(word['hebrew_analysis_may_be_incomplete'])

        split_word = next(word for word in original_text_payload('Genesis', 26, 35)['words']
                          if word['text'].startswith('וַתִּהְ'))
        self.assertEqual(
            [part['analysis_origin'] for part in split_word['word_components']],
            ['stepbible', 'inferred', 'stepbible', 'inferred'],
        )

    def test_possible_fused_ending_requires_matching_morphology_and_spelling(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        raw = 'H9001=ו=&/{H7896G=שִׁית=make}/H9034=Os3f=her'
        cases = (
            ('וְ/שַׁתִּ/הָ', 'Hc/Vqq1cs/Sp3fs', True),
            ('וְ/שַׁתִ/הָ', 'Hc/Vqq1cs/Sp3fs', False),
            ('וְ/שַׁתִּ/הָ', 'Hc/Vqq3ms/Sp3fs', False),
            ('וְ/שַׁתִּ/הָ', 'Hc/Vqq1cs', False),
        )
        for surface, grammar, expected in cases:
            with self.subTest(surface=surface, grammar=grammar):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual(
                    any(letter.get('possible_overlap_role') == 'suffix'
                        for part in parts for letter in part['letters']),
                    expected,
                )
        different_lemma = raw.replace('שִׁית', 'שָׁתַק')
        parts = _parse_hebrew_word_components(different_lemma, 'וְ/שַׁתִּ/הָ', 'Hc/Vqq1cs/Sp3fs')
        self.assertFalse(any(letter.get('possible_overlap_role') for part in parts for letter in part['letters']))

    def test_hitpael_word_components_explain_stem_prefix(self):
        word = original_text_payload('Genesis', 6, 9)['words'][11]

        self.assertEqual(
            [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
            [('prefix', 'הִֽתְ'), ('root', 'הַלֶּךְ')],
        )
        prefix, root = word['word_components'][:2]
        self.assertEqual(prefix['strongs_number'], '')
        self.assertIn('Hitpael', prefix['morphology_description'])
        self.assertIn('not a separate word', prefix['morphology_description'])
        self.assertEqual(root['strongs_number'], 'H1980I')

    def test_hitpael_components_cover_participles_and_attached_conjunctions(self):
        words = original_text_payload('Genesis', 3, 8)['words']
        self.assertEqual(
            [(part['role'], part['surface']) for part in words[5]['word_components']],
            [('prefix', 'מִתְ'), ('root', 'הַלֵּ֥ךְ')],
        )
        self.assertEqual(
            [(part['role'], part['surface']) for part in words[9]['word_components']],
            [('prefix', 'וַ'), ('prefix', 'יִּתְ'), ('root', 'חַבֵּ֨א')],
        )

    def test_imperfect_verb_person_prefixes_are_separated_from_the_root(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        word = next(
            word for word in original_text_payload('Genesis', 8, 3)['words']
            if any(candidate['strongs_number'] == 'H2637' for candidate in word['candidates'])
        )
        self.assertEqual(
            [(part['role'], part['surface']) for part in word['word_components']],
            [('prefix', 'וַ'), ('prefix', 'יַּ'), ('root', 'חְסְר֣'), ('suffix', 'וּ')],
        )

        aleph_form = _parse_hebrew_word_components(
            '{H1696=דָּבַר=to speak}',
            'אֲדַבֵּר',
            'HVqi1cs',
        )
        self.assertEqual(
            [(part['role'], part['surface']) for part in aleph_form],
            [('prefix', 'אֲ'), ('root', 'דַבֵּר')],
        )

        nun_form = _parse_hebrew_word_components(
            '{H3789=כָּתַב=to write}',
            'נִכְתֹּב',
            'HVqi1cp',
        )
        self.assertEqual(
            [(part['role'], part['surface']) for part in nun_form],
            [('prefix', 'נִ'), ('root', 'כְתֹּב')],
        )

    def test_niphal_perfect_segments_prefix_and_endings(self):
        cases = (
            ('Genesis', 3, 5, 'וְנִפְ', [
                ('prefix', 'וְ'), ('prefix', 'נִ'), ('root', 'פְקְח֖'), ('suffix', 'וּ'),
            ]),
            ('Genesis', 9, 14, 'וְנִרְאֲ', [
                ('prefix', 'וְ'), ('prefix', 'נִ'), ('root', 'רְאֲ'), ('suffix', 'תָ֥ה'),
            ]),
            ('Joshua', 7, 14, 'וְנִקְרַ', [
                ('prefix', 'וְ'), ('prefix', 'נִ'), ('root', 'קְרַבְ'), ('suffix', 'תֶּ֥ם'),
            ]),
            ('Joshua', 11, 11, 'נוֹתַ', [
                ('prefix', 'נ'), ('root', 'וֹתַ֖ר'),
            ]),
            ('Job', 21, 6, 'וְנִבְ', [
                ('prefix', 'וְ'), ('prefix', 'נִ'), ('root', 'בְהָ֑לְ'), ('suffix', 'תִּי'),
            ]),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                self.assertEqual([(part['role'], part['surface']) for part in word['word_components']], expected)

    def test_niphal_perfect_weak_forms_and_unmatched_forms(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H5358=נָקַם=avenge}', 'נִקַּמְתִּי', 'HVNp1cs',
             [('prefix', 'נִ'), ('root', 'קַּמְ'), ('suffix', 'תִּי')]),
            ('{H1540=גָּלָה=reveal}', 'נִגְלֵיתִי', 'HVNp1cs',
             [('prefix', 'נִ'), ('root', 'גְלֵי'), ('suffix', 'תִי')]),
            ('{H5352=נָקָה=clear}', 'נִקָּתָה', 'HVNp3fs',
             [('prefix', 'נִ'), ('root', 'קָּ'), ('suffix', 'תָה')]),
            ('{H5162=נָחַם=relent}', 'נִחַם', 'HVNp3ms',
             [('prefix', 'נִ'), ('root', 'חַם')]),
            ('{H5437=סָבַב=turn}', 'נָסַבּוּ', 'HVNp3cp',
             [('prefix', 'נָ'), ('root', 'סַבּ'), ('suffix', 'וּ')]),
            ('{H3498=יָתַר=remain}', 'נֹתְרוּ', 'HVNp3cp',
             [('prefix', 'נֹ'), ('root', 'תְר'), ('suffix', 'וּ')]),
            ('{H6381=פָּלָא=marvel}', 'נִפְלְאַתָה', 'HVNp3fs',
             [('prefix', 'נִ'), ('root', 'פְלְאַ'), ('suffix', 'תָה')]),
            ('{H5358=נָקַם=avenge}', 'נִקַמְתִּי', 'HVNp1cs',
             [('root', 'נִקַמְתִּי')]),
            ('{H5437=סָבַב=turn}', 'נְסַבוּ', 'HVNp3cp',
             [('root', 'נְסַבוּ')]),
            ('{H6491=פָּקַח=open}', 'נִפְקְחוּ', 'HVqp3cp',
             [('root', 'נִפְקְחוּ')]),
            ('{H3789=כָּתַב=write}', 'נִפְקְחוּ', 'HVNp3cp',
             [('root', 'נִפְקְחוּ')]),
            ('{H6491=פָּקַח=open}', 'נִפְקַח', 'HVNp3cp',
             [('root', 'נִפְקַח')]),
            ('{H3045=יָדַע=know}', 'נְוָדַע', 'HVNp3ms',
             [('root', 'נְוָדַע')]),
        )
        for raw, surface, grammar, expected in cases:
            with self.subTest(surface=surface, grammar=grammar, raw=raw):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], expected)

    def test_genesis_26_35_segments_inflections_and_section_marker(self):
        words = original_text_payload('Genesis', 26, 35)['words']
        self.assertEqual(
            [[(part['role'], part['surface']) for part in word['word_components'] if part['surface']]
             for word in words],
            [
                [('prefix', 'וַ'), ('prefix', 'תִּ'), ('root', 'הְיֶ֖י'), ('suffix', 'ןָ')],
                [('root', 'מֹ֣רַ'), ('suffix', 'ת')],
                [('root', 'ר֑וּחַ')],
                [('prefix', 'לְ'), ('root', 'יִצְחָ֖ק')],
                [('prefix', 'וּ'), ('prefix', 'לְ'), ('root', 'רִבְקָֽה'), ('grammatical', 'ס')],
            ],
        )
        self.assertEqual(words[-1]['hebrew_letters'][-1]['is_section_marker'], True)
        self.assertEqual(words[-1]['gematria_value'], 343)
        self.assertEqual(words[-1]['text'], 'וּלְרִבְקָֽה׃ ס')

    def test_inflection_splitting_is_guarded_by_grammar_and_lemma(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H7392=רָכַב=ride}', 'תִּרְכַּ֙בְנָה֙', 'HVqw3fp',
             [('prefix', 'תִּ'), ('root', 'רְכַּ֙בְ'), ('suffix', 'נָה֙')]),
            ('{H5397=נְשָׁמָה=breath}', 'נִשְׁמַ֣ת', 'HNcfsc',
             [('root', 'נִשְׁמַ֣'), ('suffix', 'ת')]),
            ('{H5397=נְשָׁמָה=breath}', 'נִשְׁמַ֣ת', 'HNcfsa',
             [('root', 'נִשְׁמַ֣ת')]),
            ('{H1980=הָלַךְ=walk}', 'תִּרְכַּ֙בְנָה֙', 'HVqw3fp',
             [('root', 'תִּרְכַּ֙בְנָה֙')]),
        )
        for raw, surface, grammar, expected in cases:
            with self.subTest(surface=surface, grammar=grammar, raw=raw):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], expected)

    def test_paragraph_marker_is_not_a_word_letter(self):
        word = original_text_payload('Genesis', 1, 5)['words'][-1]
        self.assertEqual(word['word_components'][-1]['strongs_number'], 'H9017')
        self.assertEqual(word['word_components'][-1]['role'], 'grammatical')
        self.assertTrue(word['hebrew_letters'][-1]['is_section_marker'])
        self.assertEqual(word['gematria_value'], 13)

    def test_tagged_hebrew_punctuation_is_shown_as_its_actual_symbol(self):
        cases = (
            ('Hosea', 2, 3, 'hebrew', 'H9016', '׃'),
            ('Genesis', 1, 2, 'english', 'H9014', '־'),
            ('Genesis', 1, 5, 'english', 'H9015', '׀'),
            ('Genesis', 1, 5, 'english', 'H9017', 'פ'),
            ('Genesis', 26, 35, 'english', 'H9018', 'ס'),
            ('Numbers', 10, 34, 'english', 'H9019', '׆'),
        )
        for book, chapter, verse, system, code, symbol in cases:
            with self.subTest(code=code):
                words = original_text_payload(book, chapter, verse, system)['words']
                word = next(word for word in words if any(part['strongs_number'] == code for part in word['word_components']))
                component = next(part for part in word['word_components'] if part['strongs_number'] == code)
                self.assertIn(symbol, word['text'])
                self.assertEqual(component.get('display_surface') or component['surface'], symbol)
                self.assertEqual(component['role'], 'grammatical')
                self.assertEqual(component['gematria_value'], 0)

    def test_missing_tagged_punctuation_is_not_invented(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        parts = _parse_hebrew_word_components('{H0001=אָב=father}\\H9016=׃=verseEnd', 'אָב', 'HNcmsa')
        self.assertNotIn('display_surface', parts[-1])

    def test_prepositions_and_particles_use_grammar_when_components_align(self):
        cases = (
            ('Genesis', 24, 61, 'עַל', [('grammatical', 'עַל')]),
            ('Genesis', 8, 3, 'מֵעַ', [('prefix', 'מֵ'), ('grammatical', 'עַ֥ל')]),
            ('Leviticus', 19, 18, 'לֹֽא', [('grammatical', 'לֹֽא')]),
            ('Numbers', 6, 25, 'אֵלֶ', [('grammatical', 'אֵלֶ֖י'), ('suffix', 'ךָ')]),
            ('Exodus', 20, 2, 'אֲשֶׁ', [('grammatical', 'אֲשֶׁ֧ר')]),
            ('Exodus', 20, 2, 'מֵאֶ', [('prefix', 'מֵ'), ('root', 'אֶ֥רֶץ')]),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse, start=start):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                self.assertEqual(
                    [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
                    expected,
                )

    def test_job_12_6_colors_word_parts(self):
        words = original_text_payload('Job', 12, 6)['words']
        self.assertEqual(
            [[(part['role'], part['surface']) for part in word['word_components'] if part['surface']]
             for word in words],
            [
                [('prefix', 'יִ'), ('root', 'שְׁלָ֤י'), ('suffix', 'וּ')],
                [('root', 'אֹֽהָלִ֨'), ('suffix', 'ים')],
                [('prefix', 'לְ'), ('root', 'שֹׁ֥דְדִ֗'), ('suffix', 'ים')],
                [('prefix', 'וּֽ֭'), ('root', 'בַטֻּח'), ('suffix', 'וֹת')],
                [('prefix', 'לְ'), ('prefix', 'מַ'), ('root', 'רְגִּ֣יזֵ'), ('suffix', 'י')],
                [('root', 'אֵ֑ל')],
                [('prefix', 'לַ'), ('grammatical', 'אֲשֶׁ֤ר')],
                [('prefix', 'הֵ'), ('root', 'בִ֖יא')],
                [('root', 'אֱל֣וֹהַּ')],
                [('prefix', 'בְּ'), ('root', 'יָדֽ'), ('suffix', 'וֹ')],
            ],
        )

    def test_job_12_6_inflections_require_matching_grammar_and_lemma(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H0935=בּוֹא=come}', 'הֵבִיא', 'HVqp3ms'),
            ('{H3789=כָּתַב=write}', 'הֵבִיא', 'HVhp3ms'),
            ('{H7703=שָׁדַד=ruin}', 'שֹׁדְדִים', 'HVqrmsa'),
            ('{H3789=כָּתַב=write}', 'שֹׁדְדִים', 'HVqrmpa'),
            ('{H0987=בַּטֻּחוֹת=security}', 'בַטֻּחוֹת', 'HNcfsa'),
            ('{H3789=כָּתַב=write}', 'בַטֻּחוֹת', 'HNcfpa'),
            ('{H0987=בַּטֻּחוֹת=security}', 'בַטֻּחות', 'HNcfpa'),
        )
        for raw, surface, grammar in cases:
            with self.subTest(raw=raw, surface=surface, grammar=grammar):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_hiphil_perfect_prefix_preserves_attached_object_suffix(self):
        word = next(word for word in original_text_payload('Psalms', 78, 71)['words']
                    if word['text'].startswith('הֱ֫בִיא'))
        self.assertEqual(
            [(part['role'], part['surface']) for part in word['word_components']],
            [('prefix', 'הֱ֫'), ('root', 'בִיא֥'), ('suffix', 'וֹ')],
        )
        self.assertEqual(word['word_components'][-1]['strongs_number'], 'H9033')

    def test_hiphil_participles_and_additional_imperfect_forms(self):
        cases = (
            ('Exodus', 6, 7, 'הַמּוֹצִ', [('prefix', 'הַ'), ('prefix', 'מּ'), ('root', 'וֹצִ֣יא')]),
            ('Isaiah', 8, 17, 'הַמַּסְתִּ', [('prefix', 'הַ'), ('prefix', 'מַּ'), ('root', 'סְתִּ֥יר')]),
            ('Isaiah', 8, 19, 'וְהַמַּהְ', [
                ('prefix', 'וְ'), ('prefix', 'הַ'), ('prefix', 'מַּ'), ('root', 'הְגִּ֑'), ('suffix', 'ים'),
            ]),
            ('Job', 12, 6, 'לְמַרְ', [('prefix', 'לְ'), ('prefix', 'מַ'), ('root', 'רְגִּ֣יזֵ'), ('suffix', 'י')]),
            ('Judges', 6, 12, 'וַיֵּרָ', [('prefix', 'וַ'), ('prefix', 'יֵּ'), ('root', 'רָ֥א')]),
            ('Proverbs', 3, 5, 'תִּשָּׁ', [('prefix', 'תִּ'), ('root', 'שָּׁעֵֽן')]),
            ('Joshua', 1, 9, 'תֵּחָ', [('prefix', 'תֵּ'), ('root', 'חָ֑ת')]),
            ('Ruth', 1, 16, 'תִּפְגְּ', [('prefix', 'תִּ'), ('root', 'פְגְּעִ'), ('suffix', 'י')]),
            ('Ruth', 1, 16, 'תֵּלְכִ', [('prefix', 'תֵּ'), ('root', 'לְכִ֜'), ('suffix', 'י')]),
            ('Ruth', 1, 16, 'תָּלִ', [('prefix', 'תָּ'), ('root', 'לִ֙ינִ'), ('suffix', 'י֙')]),
            ('Joshua', 1, 9, 'צִוִּ', [('root', 'צִוִּי'), ('suffix', 'תִ֙י'), ('suffix', 'ךָ֙')]),
            ('Malachi', 3, 6, 'בְּנֵ', [('root', 'בְּנֵֽ'), ('suffix', 'י')]),
            ('Isaiah', 8, 19, 'דִּרְשׁ', [('root', 'דִּרְשׁ֤'), ('suffix', 'וּ')]),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse, start=start):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                self.assertEqual(
                    [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
                    expected,
                )

    def test_hiphil_participle_does_not_split_nominal_or_unmatched_lemmas(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H4945=מַשְׁקֶה=cupbearer}', 'מַשְׁקֶה', 'HVhrmsa'),
            ('{H3789=כָּתַב=write}', 'מּוֹצִיא', 'HVhrmsa'),
            ('{H3318=יָצָא=go out}', 'מּוֹצִיא', 'HVqrmsa'),
            ('{H3789=כָּתַב=write}', 'תִּפְגְּעִי', 'HVqi2fs'),
            ('{H1696=דָּבַר=speak}', 'מּוֹצִיא', 'HVhrmsa'),
            ('{H3789=כָּתַב=write}', 'צִוִּיתִי', 'HVpp1cs'),
            ('{H2865=חָתַת=be dismayed}', 'תֵּחֶת', 'HVNj2ms'),
            ('{H4945=מַשְׁקֶה=cupbearer}', 'מַשְׁקִים', 'HVhrmpa'),
            ('{H1121=בֵּן=son}', 'בְּנֵי', 'HNcmsc'),
            ('{H1875=דָּרַשׁ=seek}', 'דִּרְשׁו', 'HVqv2mp'),
        )
        for raw, surface, grammar in cases:
            with self.subTest(surface=surface, grammar=grammar, raw=raw):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_construct_ending_preserves_tagged_possessive_suffix(self):
        word = next(
            word for word in original_text_payload('Genesis', 2, 2)['words']
            if any(candidate['strongs_number'] == 'H4399' for candidate in word['candidates'])
        )
        self.assertEqual(
            [(part['role'], part['surface']) for part in word['word_components']],
            [('root', 'מְלַאכְ'), ('suffix', 'תּ֖'), ('suffix', 'וֹ')],
        )
        self.assertEqual(word['word_components'][-1]['strongs_number'], 'H9023')

    def test_irregular_daughter_plural_preserves_prefixes_and_possessive_suffixes(self):
        cases = (
            (28, 1, [('prefix', 'מִ'), ('root', 'בְּנ֥'), ('suffix', 'וֹת')]),
            (28, 2, [('prefix', 'מִ'), ('root', 'בְּנ֥'), ('suffix', 'וֹת')]),
            (19, 8, [('root', 'בָנ֗'), ('suffix', 'וֹת')]),
            (31, 26, [('root', 'בְּנֹ'), ('suffix', 'תַ֔'), ('suffix', 'י')]),
            (19, 14, [('root', 'בְנֹ'), ('suffix', 'תָ֗י'), ('suffix', 'ו')]),
            (31, 31, [('root', 'בְּנ'), ('suffix', 'וֹתֶ֖י'), ('suffix', 'ךָ')]),
            (29, 18, [('root', 'בִּתְּ'), ('suffix', 'ךָ֖')]),
        )
        for chapter, verse, expected in cases:
            with self.subTest(chapter=chapter, verse=verse):
                word = next(word for word in original_text_payload('Genesis', chapter, verse)['words']
                            if any(part['strongs_number'].startswith('H1323')
                                   for part in word['word_components']))
                self.assertEqual(
                    [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
                    expected,
                )

    def test_irregular_daughter_plural_requires_matching_lemma_and_grammar(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H1323G=בַּת=daughter}', 'בְּנוֹת', 'HNcfsa'),
            ('{H1121=בַּת=other}', 'בְּנוֹת', 'HNcfpc'),
            ('{H1323G=אֵם=mother}', 'בְּנוֹת', 'HNcfpc'),
            ('{H1323G=בַּת=daughter}', 'בְּנוֹת', 'HNcmpa'),
        )
        for raw, surface, grammar in cases:
            with self.subTest(raw=raw, surface=surface, grammar=grammar):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_irregular_sister_plural_preserves_possessives_and_singular(self):
        cases = (
            ('Job', 1, 4, [('root', 'אַחְיֽ'), ('suffix', 'וֹתֵי'), ('suffix', 'הֶ֔ם')]),
            ('Joshua', 2, 13, [('root', 'אַחְי'), ('suffix', 'וֹתַ֔'), ('suffix', 'י')]),
            ('ChroniclesFirstBook', 2, 16, [
                ('prefix', 'וְ'), ('root', 'אַחְי'), ('suffix', 'וֹתֵי'), ('suffix', 'הֶ֖ם'),
            ]),
            ('Hosea', 2, 1, [
                ('prefix', 'וְ'), ('prefix', 'לַ'), ('root', 'אֲחֽ'), ('suffix', 'וֹתֵי'), ('suffix', 'כֶ֖ם'),
            ]),
            ('Ezekiel', 16, 52, [('root', 'אַחְי'), ('suffix', 'וֹתֵֽ'), ('suffix', 'ךְ')]),
            ('Exodus', 2, 4, [('root', 'אֲחֹת֖'), ('suffix', 'וֹ')]),
        )
        for book, chapter, verse, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse):
                word = next(word for word in reversed(original_text_payload(book, chapter, verse)['words'])
                            if any(part['strongs_number'].startswith('H0269')
                                   for part in word['word_components']))
                self.assertEqual(
                    [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
                    expected,
                )

    def test_sister_plural_requires_matching_lemma_and_grammar(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        for raw, grammar in (
            ('{H0269=אָחוֹת=sister}', 'HNcfsc'),
            ('{H0269=אָחוֹת=sister}', 'HNcmpc'),
            ('{H1323=אָחוֹת=other}', 'HNcfpc'),
            ('{H0269=בַּת=other}', 'HNcfpc'),
        ):
            with self.subTest(raw=raw, grammar=grammar):
                parts = _parse_hebrew_word_components(raw, 'אַחְיוֹתֵי', grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', 'אַחְיוֹתֵי')])

    def test_additional_inflections_found_in_old_testament_samples(self):
        cases = (
            ('Genesis', 4, 22, 'יָֽלְדָ', [('root', 'יָֽלְדָ'), ('suffix', 'ה֙')]),
            ('Exodus', 2, 4, 'וַתֵּתַ', [
                ('prefix', 'וַ'), ('prefix', 'תֵּתַ'), ('root', 'צַּ֥ב'),
            ]),
            ('Deuteronomy', 4, 2, 'תֹסִ', [('prefix', 'תֹ'), ('root', 'סִ֗פ'), ('suffix', 'וּ')]),
            ('Deuteronomy', 4, 2, 'מְצַו', [('prefix', 'מְ'), ('root', 'צַוֶּ֣ה')]),
            ('Joshua', 2, 13, 'וְהִצַּ', [
                ('prefix', 'וְ'), ('prefix', 'הִ'), ('root', 'צַּלְ'), ('suffix', 'תֶּ֥ם'),
            ]),
            ('KingsSecondBook', 6, 16, 'רַבִּ', [('root', 'רַבִּ'), ('suffix', 'ים֙')]),
            ('Ruth', 2, 12, 'שְׁלֵמָ', [('root', 'שְׁלֵמָ֗'), ('suffix', 'ה')]),
            ('Ruth', 2, 12, 'כְּנָפָ', [('root', 'כְּנָפָֽ'), ('suffix', 'י'), ('suffix', 'ו')]),
            ('Ezekiel', 16, 52, 'שְׂאִ', [('root', 'שְׂאִ֣'), ('suffix', 'י')]),
            ('Ezekiel', 16, 52, 'בְּחַטֹּא', [
                ('prefix', 'בְּ'), ('root', 'חַטֹּא'), ('suffix', 'תַ֛יִ'), ('suffix', 'ךְ'),
            ]),
            ('Hosea', 2, 3, 'עֲרֻמָּ', [('root', 'עֲרֻמָּ֔'), ('suffix', 'ה')]),
            ('Hosea', 2, 3, 'הִוָּ', [
                ('prefix', 'הִ'), ('root', 'וָּֽלְדָ֑'), ('suffix', 'הּ'),
            ]),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse, start=start):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                self.assertEqual(
                    [(part['role'], part['surface']) for part in word['word_components'] if part['surface']],
                    expected,
                )

    def test_additional_inflections_require_matching_grammar_and_stems(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H6213=עָשָׂה=do}', 'עָשָׂה', 'HVqp3fs'),
            ('{H3205=יָלַד=bear}', 'יָלְדָה', 'HVqp3ms'),
            ('{H5337=נָצַל=rescue}', 'הִצַלְתֶּם', 'HVhq2mp'),
            ('{H3254=יָסַף=add}', 'תַסִפוּ', 'HVhi2mp'),
            ('{H6680=צָוָה=command}', 'מְצַוֶּה', 'HVqrmsa'),
            ('{H7227=רַב=many}', 'רַבִּים', 'HNcmsa'),
            ('{H7227=רַב=many}', 'רַבִּים', 'HAafsa'),
            ('{H3789=כָּתַב=write}', 'שְׂאִי', 'HVqv2fs'),
            ('{H3320=יָצַב=stand}', 'תֵּתַצַּב', 'HVtw3ms'),
            ('{H2403=חַטָּאת=sin}', 'חַטֹּאתַיִ', 'HNcfsc'),
            ('{H0269=אָחוֹת=sister}', 'אַחְיוֹתֵי', 'HNcfsc'),
            ('{H3671=כָּנָף=wing}', 'כְּנָפָי', 'HNcfsc'),
            ('{H3205=יָלַד=bear}', 'הִוָּלְדָ', 'HVqcc'),
            ('{H3205=כָּתַב=write}', 'הִוָּלְדָ', 'HVNcc'),
        )
        for raw, surface, grammar in cases:
            with self.subTest(raw=raw, surface=surface, grammar=grammar):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_dual_absolute_ending_is_separated_only_for_dual_grammar(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        raw = '{H3671=כָּנָף=wing}'
        surface = 'כְּנָפַיִם'
        parts = _parse_hebrew_word_components(raw, surface, 'HNcfda')
        self.assertEqual([(part['role'], part['surface']) for part in parts], [
            ('root', 'כְּנָפַ'), ('suffix', 'יִם'),
        ])
        parts = _parse_hebrew_word_components(raw, surface, 'HNcfsa')
        self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_torah_inflections_preserve_lexical_and_grammatical_parts(self):
        cases = (
            ('Genesis', 8, 3, 'וַיָּשׁ', [('prefix', 'וַ'), ('prefix', 'יָּ'), ('root', 'שֻׁ֧ב'), ('suffix', 'וּ')]),
            ('Exodus', 20, 2, 'הוֹצֵא', [('prefix', 'ה'), ('root', 'וֹצֵא'), ('suffix', 'תִ֛י'), ('suffix', 'ךָ')]),
            ('Leviticus', 26, 36, 'מְנֻ', [('root', 'מְנֻֽסַ'), ('suffix', 'ת')]),
            ('Numbers', 6, 24, 'יְבָרֶ', [('prefix', 'יְ'), ('root', 'בָרֶכְ'), ('suffix', 'ךָ֥')]),
            ('Deuteronomy', 6, 5, 'וְאָ֣הַב', [('prefix', 'וְ'), ('root', 'אָ֣הַבְ'), ('suffix', 'תָּ֔')]),
            ('Genesis', 2, 2, 'וַיִּשְׁ', [('prefix', 'וַ'), ('prefix', 'יִּ'), ('root', 'שְׁבֹּת֙')]),
            ('Genesis', 24, 61, 'וַתִּרְ', [('prefix', 'וַ'), ('prefix', 'תִּ'), ('root', 'רְכַּ֙בְ'), ('suffix', 'נָה֙')]),
            ('Exodus', 20, 12, 'יַאֲרִ', [('prefix', 'יַ'), ('root', 'אֲרִכ֣'), ('suffix', 'וּ'), ('suffix', 'ן')]),
            ('Exodus', 6, 7, 'וִֽידַע', [('prefix', 'וִֽ'), ('root', 'ידַעְ'), ('suffix', 'תֶּ֗ם')]),
            ('Leviticus', 19, 18, 'וְאָֽהַב', [('prefix', 'וְ'), ('root', 'אָֽהַבְ'), ('suffix', 'תָּ֥')]),
            ('Leviticus', 19, 3, 'תִּשְׁ', [('prefix', 'תִּ'), ('root', 'שְׁמֹ֑ר'), ('suffix', 'וּ')]),
            ('Numbers', 6, 25, 'יָאֵ', [('prefix', 'יָ'), ('root', 'אֵ֨ר')]),
            ('Numbers', 15, 40, 'וַעֲשׂ', [('prefix', 'וַ'), ('root', 'עֲשִׂי'), ('suffix', 'תֶ֖ם')]),
            ('Deuteronomy', 5, 16, 'אָבִ', [('root', 'אָבִ֙י'), ('suffix', 'ךָ֙')]),
            ('Deuteronomy', 5, 16, 'יַאֲרִ', [('prefix', 'יַ'), ('root', 'אֲרִיכֻ֣'), ('suffix', 'ן')]),
            ('Deuteronomy', 6, 4, 'אֱלֹהֵ', [('root', 'אֱלֹהֵ֖י'), ('suffix', 'נוּ')]),
            ('Leviticus', 26, 36, 'וְהַנִּשְׁ', [
                ('prefix', 'וְ'), ('prefix', 'הַ'), ('prefix', 'נִּ'),
                ('root', 'שְׁאָרִ֣'), ('suffix', 'ים'),
            ]),
            ('Genesis', 24, 61, 'וַתֵּלַ', [('prefix', 'וַ'), ('prefix', 'תֵּ'), ('root', 'לַ֖כְ'), ('suffix', 'נָה')]),
            ('Genesis', 24, 61, 'וַיִּקַּ', [('prefix', 'וַ'), ('prefix', 'יִּ'), ('root', 'קַּ֥ח')]),
            ('Genesis', 24, 61, 'וְנַעֲ', [('prefix', 'וְ'), ('root', 'נַעֲרֹ'), ('suffix', 'תֶ֗י'), ('suffix', 'הָ')]),
            ('Leviticus', 19, 18, 'תִקֹּ', [('prefix', 'תִ'), ('root', 'קֹּ֤ם')]),
            ('Numbers', 6, 25, 'וִֽיחֻ', [
                ('prefix', 'וִֽ'), ('prefix', 'י'), ('root', 'חֻנֶּֽ'), ('suffix', 'ךָּ'), ('grammatical', 'ס'),
            ]),
        )
        for book, chapter, verse, start, expected in cases:
            with self.subTest(book=book, chapter=chapter, verse=verse, start=start):
                word = next(word for word in original_text_payload(book, chapter, verse)['words']
                            if word['text'].startswith(start))
                parts = [(part['role'], part['surface']) for part in word['word_components'] if part['surface']]
                self.assertEqual(parts, expected)

    def test_inflection_rules_leave_unmatched_or_incompatible_forms_intact(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        cases = (
            ('{H3045=יָדַע=know}', 'יְדַעְתֶּן', 'HVqp2fp',
             [('root', 'יְדַעְ'), ('suffix', 'תֶּן')]),
            ('{H3045=יָדַע=know}', 'יְדַעְתֶּן', 'HVqp3ms',
             [('root', 'יְדַעְתֶּן')]),
            ('{H3789=כָּתַב=write}', 'יְדַעְתֶּם', 'HVqp2mp',
             [('root', 'יְדַעְתֶּם')]),
            ('{H7604=שָׁאַר=remain}', 'נִשְׁאָרִים', 'HVqrmpa',
             [('root', 'נִשְׁאָרִים')]),
            ('{H3789=כָּתַב=write}', 'נִשְׁאָרִים', 'HVNrmpa',
             [('root', 'נִשְׁאָרִים')]),
            ('{H5358=נָקַם=avenge}', 'תִקֹם', 'HVqi2ms',
             [('root', 'תִקֹם')]),
            ('{H2603=חָנַן=be gracious}', 'יְחַנֶךָ', 'HVqi3ms',
             [('root', 'יְחַנֶךָ')]),
            ('{H0748=אָרַךְ=lengthen}', 'יַאֲרִיַכְ', 'HVhj3ms',
             [('root', 'יַאֲרִיַכְ')]),
        )
        for raw, surface, grammar, expected in cases:
            with self.subTest(surface=surface, grammar=grammar, raw=raw):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], expected)

    def test_stem_prefix_splitting_requires_morphology_and_matching_root(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        for grammar, surface in (('HVqp3ms', 'הִתְהַלֶּךְ'), ('HVtp3ms', 'הִתְחַבֵּא')):
            with self.subTest(grammar=grammar, surface=surface):
                parts = _parse_hebrew_word_components('{H1980I=הָלַךְ=walk}', surface, grammar)
                self.assertEqual([(part['role'], part['surface']) for part in parts], [('root', surface)])

    def test_hebrew_letter_sounds_include_vowels_and_shin_dot(self):
        from walkasjesus_app.lib.strongs_service import _hebrew_letter_data

        for glyph, name, sound in (
            ('שָׁ', 'Shin', 'shā'), ('שָׁ', 'Shin', 'shā'),
            ('שָׂ', 'Sin', 'sā'), ('בַּ', 'Bet', 'ba'),
            ('וּ', 'Vav', 'ū'), ('וֹ', 'Vav', 'ō'),
        ):
            with self.subTest(glyph=glyph):
                letter = _hebrew_letter_data(glyph)[0]
                self.assertEqual(letter['name'], name)
                self.assertEqual(letter['sound'], sound)

    def test_hebrew_word_details_include_affixes_letters_and_gematria(self):
        leviticus_word = original_text_payload('Leviticus', 26, 36)['words'][1]

        self.assertEqual(leviticus_word['gematria_value'], 62)
        self.assertEqual(
            [(part['role'], part['surface']) for part in leviticus_word['word_components']],
            [('prefix', 'בָּ'), ('suffix', 'כֶ֔ם')],
        )
        self.assertEqual(
            leviticus_word['word_components'][1]['morphology_description'],
            'Object suffix: 2nd person masculine plural',
        )
        self.assertEqual([letter['value'] for letter in leviticus_word['hebrew_letters']], [2, 20, 40])

        genesis_word = original_text_payload('Genesis', 1, 1)['words'][0]
        self.assertEqual(genesis_word['gematria_value'], 913)
        self.assertEqual([part['role'] for part in genesis_word['word_components']], ['prefix', 'root'])
        self.assertEqual(
            [item['description'] for item in genesis_word['grammar_details']],
            ['preposition', 'common noun, feminine, singular, absolute'],
        )

        dutch_genesis_word = localized_original_text_payload('Genesis', 1, 1, 'nl')['words'][0]
        self.assertEqual(dutch_genesis_word['word_components'][1]['local_gloss'], 'beginne')

    def test_service_meanings_are_separate_from_occurrence_glosses(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        genesis = localized_original_text_payload('Genesis', 1, 1, 'nl')['words'][0]
        prefix = genesis['word_components'][0]
        self.assertEqual(prefix['strongs_number'], 'H9003')
        self.assertEqual(prefix['gloss'], 'in')
        self.assertIn('met', prefix['possible_meanings']['nl'].split(', '))
        self.assertEqual(genesis['word_components'][1]['local_gloss'], 'beginne')

        conjunction = original_text_payload('Genesis', 1, 3)['words'][0]['word_components'][0]
        self.assertEqual(conjunction['strongs_number'], 'H9001')
        self.assertEqual(conjunction['possible_meanings']['nl'].split(', '), [
            'en', 'maar', 'opdat', 'zodat', 'doordat',
        ])
        other_conjunction = original_text_payload('Genesis', 1, 2)['words'][0]['word_components'][0]
        self.assertEqual(other_conjunction['possible_meanings'], conjunction['possible_meanings'])
        for code, letter, gloss, meaning in (
            ('H9004', 'כ', 'like', 'zoals'),
            ('H9005', 'ל', 'to', 'voor'),
            ('H9006', 'מ', 'from', 'uit'),
        ):
            with self.subTest(code=code):
                part = _parse_hebrew_word_components(f'{code}={letter}={gloss}')[0]
                self.assertIn(meaning, part['possible_meanings']['nl'].split(', '))

    def test_waw_suffix_meanings_follow_morphology_not_the_letter_alone(self):
        from walkasjesus_app.lib.strongs_service import _parse_hebrew_word_components

        for raw, surface, grammar, expected in (
            ('{H3027=יָד=hand}/H9023=Ps3m=his', 'יָד/וֹ', 'HNcmsc/Sp3ms', 'zijn'),
            ('H9005=ל=to/{H9033=Os3m=him}', 'ל/וֹ', 'HR/Sp3ms', 'hem'),
            ('{H3205=יָלַד=beget}/H9043=Ss3m=he', 'הוֹלִיד/וֹ', 'HVhcc/Sp3ms', 'hij'),
            ('{H1980=הָלַךְ=walk}', 'הָלְכוּ', 'HVqp3cp', 'zij'),
            ('{H1980=הָלַךְ=walk}', 'הִלְכוּ', 'HVqv2mp', 'jullie'),
        ):
            with self.subTest(grammar=grammar):
                parts = _parse_hebrew_word_components(raw, surface, grammar)
                suffix = parts[-1]
                self.assertEqual(suffix['role'], 'suffix')
                self.assertIn(expected, suffix['possible_meanings']['nl'])

        directional = _parse_hebrew_word_components(
            '{H0776=אֶרֶץ=land}/H9011=ה=to', 'אַרְצָ/ה', 'HNcfsa/Sd'
        )[-1]
        self.assertEqual(directional['role'], 'suffix')
        self.assertIn('naar', directional['possible_meanings']['nl'])
        subject_suffix = original_text_payload('Genesis', 2, 4)['words'][4]['word_components'][-1]
        self.assertEqual(subject_suffix['strongs_number'], 'H9048')
        self.assertEqual(subject_suffix['role'], 'suffix')

    @patch('walkasjesus_app.views.user_preferences._translate_google_batch')
    def test_dutch_payload_localizes_grammatical_component_glosses(self, mock_translate_batch):
        cache.clear()
        mock_translate_batch.side_effect = lambda texts, language: [f'NL: {text}' for text in texts]
        word = localized_original_text_payload('Leviticus', 26, 36, 'nl')['words'][1]

        self.assertEqual([part['local_gloss'] for part in word['word_components']], ['NL: in', 'jullie'])
        self.assertTrue(word['word_components'][1]['local_description'].startswith('NL: '))
        self.assertNotEqual(
            word['word_components'][1]['local_description'],
            word['word_components'][1]['morphology_description'],
        )
        self.assertTrue(all(item['local_description'].startswith('NL: ') for item in word['grammar_details']))

        genesis = localized_original_text_payload('Genesis', 1, 1, 'nl')['words'][0]
        self.assertEqual(genesis['local_gloss'], 'beginne')
        self.assertEqual(genesis['word_components'][1]['local_gloss'], 'beginne')

    def test_dutch_payload_adds_statenvertaling_glosses_and_usage(self):
        payload = localized_original_text_payload('Exodus', 1, 1, 'nl')
        words = payload['words']

        self.assertEqual(payload['local_language'], 'nl')
        self.assertEqual(words[2]['local_gloss'], 'zonen')
        # Untagged words still fall back to the most common Statenvertaling rendering.
        self.assertTrue(all(word['local_gloss'] for word in words if word['has_candidates']))

        candidate = words[2]['candidates'][0]
        usage = candidate['local_usage']
        self.assertGreater(len(usage), 3)
        self.assertIn('zoon', [item['label'] for item in usage])
        self.assertGreater(usage[0]['count'], usage[-1]['count'])
        self.assertGreater(len(usage[0]['references']), 100)

        # Hebrew usage outline nodes have non-zero counts and references
        self.assertGreater(candidate['usage_outline'][0]['count'], 0)
        self.assertGreater(len(candidate['usage_outline'][0]['references']), 0)

    def test_english_payload_is_unchanged(self):
        payload = localized_original_text_payload('Exodus', 1, 1, 'en')

        self.assertNotIn('local_language', payload)
        self.assertNotIn('local_gloss', payload['words'][2])


class LocalStatenvertalingBibleTestCase(SimpleTestCase):
    def test_serves_verses_from_bundled_data(self):
        bible = LocalStatenvertalingBible('svv-statenvertaling')

        self.assertEqual(bible.language, 'nl')
        self.assertEqual(bible.abbreviation, 'SV')
        self.assertTrue(bible.is_local_source)
        self.assertEqual(
            bible.verses(BibleLibBibleBooks['Genesis'], 1, 1, 1, 1),
            'In den beginne schiep God den hemel en de aarde.',
        )

    def test_is_registered_as_a_selectable_translation(self):
        bible_ids = {getattr(bible, 'id', '') for bible in BibleTranslation().all()}

        self.assertIn('svv-statenvertaling', bible_ids)


class StrongsServiceFallbackTestCase(TestCase):
    @patch('walkasjesus_app.lib.strongs_service._stepbible_rows_for_verse', return_value=[])
    def test_original_text_payload_uses_non_clickable_fallback_for_missing_stepbible_rows(self, _mock_rows):
        payload = original_text_payload('Psalms', 3, 2)

        self.assertGreater(len(payload['words']), 0)
        self.assertTrue(all(not word['clickable'] for word in payload['words']))
        self.assertTrue(all(not word['has_candidates'] for word in payload['words']))
        self.assertTrue(all(not word['detail_note'] for word in payload['words']))

    def test_step_references_preserve_primary_numbering_with_hebrew_annotations(self):
        for source, expected in (
            ('Psa.51.7(51.9)', 'Psa.51:7'),
            ('Psa.3.2(3.3)', 'Psa.3:2'),
            ('Mal.4.1(3.19)', 'Mal.4:1'),
            ('Gen.1.1', 'Gen.1:1'),
            ('Jhn.3.16', 'Jhn.3:16'),
        ):
            with self.subTest(reference=source):
                self.assertEqual(_step_reference_to_display(source), expected)

    @patch('walkasjesus_app.lib.strongs_service.BibleTranslation')
    def test_psalm_51_verses_have_tagged_hebrew_and_strongs_details(self, mock_bibles):
        mock_bibles.return_value.get.return_value = SimpleNamespace(
            name='Westminster Leningrad Codex',
            verses=lambda *args: '',
        )
        for verse in range(7, 12):
            with self.subTest(verse=verse):
                rows = _stepbible_rows_for_verse('Psalms', 51, verse)
                self.assertGreater(len(rows), 0)
                self.assertTrue(all(row.startswith(f'Psa.51.{verse}(') for row in rows))
                payload = original_text_payload('Psalms', 51, verse)
                self.assertGreater(len(payload['words']), 0)
                self.assertTrue(any(word['clickable'] and word['has_candidates'] for word in payload['words']))
                self.assertTrue(all(word['tagging_source'] == 'STEPBible' for word in payload['words']))
                self.assertIsNotNone(payload['selected_word'])
                self.assertTrue(payload['selected_word']['grammar'])
        verse_seven = original_text_payload('Psalms', 51, 7)
        self.assertTrue(any(
            candidate['strongs_number'] == 'H0231'
            for word in verse_seven['words']
            for candidate in word['candidates']
        ))

    def test_candidate_payload_exposes_structured_detail_sections(self):
        candidate = _candidate_payload('G5083', 'greek', {})
        derived_candidate = _candidate_payload('G1301', 'greek', {})
        hebrew_candidate = _candidate_payload('H8104', 'hebrew', {})

        self.assertIn('to watch over, guard, keep, preserve', candidate['outline_meanings'])
        self.assertGreater(len(candidate['reference_groups']), 0)
        self.assertTrue(all(len(group) <= 3 for group in candidate['reference_groups']))
        self.assertGreater(len(candidate['translation_counts']), 0)
        self.assertEqual(candidate['translation_counts'][0]['label'], 'to watch over, guard, keep, preserve')
        self.assertGreater(candidate['translation_counts'][0]['count'], 0)
        self.assertGreater(len(candidate['usage_outline']), 0)
        self.assertEqual(candidate['usage_outline'][0]['label'], 'to watch over, guard, keep, preserve')
        self.assertGreater(candidate['usage_outline'][0]['count'], 0)
        self.assertEqual(candidate['usage_outline'][0]['count'], len(candidate['usage_outline'][0]['references']))
        self.assertTrue(all(len(group) <= 3 for group in candidate['usage_outline'][0]['reference_groups']))
        self.assertTrue(candidate['kjv_definition'])
        self.assertTrue(any(root_word['strongs_number'] == 'G5083' for root_word in derived_candidate['root_words']))
        self.assertGreater(len(hebrew_candidate['translation_counts']), 0)
        self.assertGreater(hebrew_candidate['translation_counts'][0]['count'], 0)
        self.assertGreater(len(hebrew_candidate['usage_outline']), 0)
        self.assertGreater(len(hebrew_candidate['references']), 0)
        self.assertTrue(any(reference.startswith('Gen.') for reference in hebrew_candidate['references']))

    def test_candidate_payload_uses_nested_lexicon_outline_for_hebrew_examples(self):
        peace_candidate = _candidate_payload('H7965', 'hebrew', {})
        life_candidate = _candidate_payload('H2416', 'hebrew', {})
        tree_candidate = _candidate_payload('H6086', 'hebrew', {})
        knowledge_candidate = _candidate_payload('H1847', 'hebrew', {})

        self.assertEqual(peace_candidate['usage_outline'][0]['label'], 'completeness, soundness, welfare, peace')
        self.assertIn('peace, friendship', [child['label'] for child in peace_candidate['usage_outline'][0]['children']])
        friendship = next(child for child in peace_candidate['usage_outline'][0]['children'] if child['label'] == 'peace, friendship')
        self.assertIn('with God especially in covenant relationship', [child['label'] for child in friendship['children']])

        life_labels = [item['label'] for item in life_candidate['usage_outline']]
        self.assertIn('living, alive', life_labels)
        self.assertIn('kinsfolk', life_labels)
        self.assertIn('living thing, animal', life_labels)
        self.assertIn('life (abstract emphatic)', life_labels)
        living = next(item for item in life_candidate['usage_outline'] if item['label'] == 'living, alive')
        self.assertIn('green (of vegetation)', [child['label'] for child in living['children']])
        self.assertEqual(living['grammar_label'], 'adjective')

        self.assertEqual(tree_candidate['usage_outline'][0]['label'], 'tree, wood, timber, stock, plank, stalk, stick, gallows')
        self.assertIn('wood, pieces of wood, gallows, firewood, cedar-wood, woody flax', [child['label'] for child in tree_candidate['usage_outline'][0]['children']])

        self.assertEqual(knowledge_candidate['usage_outline'][0]['label'], 'knowledge')
        self.assertIn('discernment, understanding, wisdom', [child['label'] for child in knowledge_candidate['usage_outline'][0]['children']])

    def test_candidate_payload_uses_marker_outline_for_greek_example(self):
        candidate = _candidate_payload('G4137', 'greek', {})

        self.assertEqual(candidate['usage_outline'][0]['label'], 'to fill, make full, fill to the full, with accusative')
        self.assertIn('of things', [child['label'] for child in candidate['usage_outline'][0]['children']])
        self.assertEqual(candidate['usage_outline'][1]['label'], 'to complete')
        self.assertIn('to execute, accomplish, carry out to the full', [child['label'] for child in candidate['usage_outline'][1]['children']])
        execute = next(child for child in candidate['usage_outline'][1]['children'] if child['label'] == 'to execute, accomplish, carry out to the full')
        self.assertEqual(execute['count'], len(execute['references']))
        self.assertGreater(len(execute['references']), 20)

    def test_candidate_payload_normalizes_leading_zero_greek_strongs_and_avoids_step_artifacts(self):
        candidate = _candidate_payload('G0906', 'greek', {})

        self.assertEqual(candidate['usage_outline'][0]['label'], 'to throw, cast, put, place')
        self.assertNotIn('»', candidate['kjv_definition'])
        self.assertIn('throw', candidate['kjv_definition'])
        self.assertEqual(candidate['first_reference'], 'Mat.3:10')

    def test_original_text_word_label_prefers_kjv_definition(self):
        payload = original_text_payload('Matthew', 1, 1)
        first_word = payload['words'][0]
        abraham = next(word for word in payload['words'] if word['text'].startswith('Ἀβρα'))

        self.assertEqual(first_word['translation_label'], 'book')
        self.assertEqual(first_word['candidates'][0]['kjv_definition'], 'book')
        self.assertNotEqual(first_word['translation_label'], first_word['candidates'][0]['usage_outline'][0]['label'])
        self.assertEqual(abraham['translation_label'], 'Abraham')
        self.assertNotIn('»', abraham['translation_label'])
        self.assertEqual(abraham['candidates'][0]['strongs_number'], 'G0011')

    def test_candidate_payload_skips_name_only_hebrew_variants_in_outline(self):
        candidate = _candidate_payload('H6965', 'hebrew', {})

        self.assertEqual(candidate['usage_outline'][0]['label'], 'to rise, arise, stand, rise up, stand up')
        self.assertNotIn('Combined with lev', candidate['usage_outline'][0]['label'])

    @patch('walkasjesus_app.lib.strongs_service._lxx_greek_to_hebrew_index')
    def test_candidate_payload_exposes_lxx_hebrew_equivalents_when_index_exists(self, mock_lxx_index):
        mock_lxx_index.return_value = {
            'G3056': {
                'greekStrong': 'G3056',
                'greekLemma': 'λόγος',
                'hebrewCandidates': [
                    {
                        'strong': 'H1697',
                        'lemma': 'דבר',
                        'transliteration': 'dabar',
                        'count': 842,
                        'percentage': 81.4,
                        'confidence': 94,
                    },
                    {
                        'strong': 'H0565',
                        'lemma': 'אמר',
                        'transliteration': 'amar',
                        'count': 103,
                        'percentage': 9.9,
                        'confidence': 63,
                    },
                ],
            }
        }

        candidate = _candidate_payload('G3056', 'greek', {})

        self.assertEqual(candidate['lxx_hebrew_equivalents'][0]['strong'], 'H1697')
        self.assertEqual(candidate['lxx_hebrew_equivalents'][0]['confidence'], 94)
        self.assertTrue(candidate['lxx_hebrew_equivalents'][0]['first_reference'])
        self.assertEqual(candidate['lxx_hebrew_equivalents'][1]['transliteration'], 'amar')
        self.assertTrue(candidate['lxx_hebrew_equivalents'][0]['definition'])
        self.assertGreater(len(candidate['lxx_hebrew_equivalents'][0]['possible_meanings']), 0)
        self.assertGreater(len(candidate['lxx_hebrew_equivalents'][0]['usage_outline']), 0)
        self.assertIn('/lexicon/h1697/', candidate['lxx_hebrew_equivalents'][0]['blueletter_url'])

    def test_original_text_payload_dedupes_normalized_strongs_candidates(self):
        payload = original_text_payload('JohnFirstBook', 2, 3)

        for word in payload['words']:
            codes = [candidate['strongs_number'] for candidate in word['candidates']]
            self.assertEqual(codes, list(dict.fromkeys(codes)))

        g1097_words = [
            word for word in payload['words']
            if any(candidate['strongs_number'] == 'G1097' for candidate in word['candidates'])
        ]
        self.assertEqual(len(g1097_words), 2)
        self.assertTrue(all(
            [candidate['strongs_number'] for candidate in word['candidates']].count('G1097') == 1
            for word in g1097_words
        ))

    @patch('walkasjesus_app.lib.strongs_service._variant_step_codes')
    @patch('walkasjesus_app.lib.strongs_service._stepbible_usage_index')
    @patch('walkasjesus_app.lib.strongs_service._lookup_step_lexicon_entry')
    @patch('walkasjesus_app.lib.strongs_service._lookup_open_scriptures_entry')
    def test_hebrew_fallback_occurrence_labels_use_lexicon_label_when_no_variant_labels_exist(
        self,
        mock_open_scriptures,
        mock_lookup_lexicon,
        mock_usage_index,
        mock_variant_step_codes,
    ):
        mock_variant_step_codes.return_value = []
        mock_usage_index.return_value = {
            'exact': {},
            'base': {'H9999': ['Gen.1:1', 'Gen.1:2']},
        }
        mock_open_scriptures.return_value = {
            'strongs_def': 'to test',
            'kjv_def': 'test',
        }
        mock_lookup_lexicon.return_value = {
            'lemma': 'נסה',
            'transliteration': 'nasah',
            'grammar': 'H:V',
            'short_gloss': 'to test',
            'definition': 'to test',
            'full_entry': '',
            'references': [],
        }

        candidate = _candidate_payload('H9999', 'hebrew', {})

        self.assertEqual(candidate['translation_counts'][0]['label'], 'to test')
        self.assertIn('to test', candidate['outline_meanings'])
        self.assertEqual(candidate['usage_outline'][0]['label'], 'to test')
        self.assertEqual(candidate['usage_outline'][0]['count'], 2)


class LocalCompleteJewishBibleTestCase(SimpleTestCase):
    def tearDown(self):
        LocalCompleteJewishBible._index = None
        super().tearDown()

    def test_local_cjb_translation_uses_cjb_ot_and_jnt_verse_text(self):
        LocalCompleteJewishBible._index = None
        bible = LocalCompleteJewishBible('cjb-bible-com')

        genesis = bible.verses(BibleLibBibleBooks.Genesis, 1, 1, 1, 1)
        matthew = bible.verses(BibleLibBibleBooks.Matthew, 1, 1, 1, 1)

        self.assertEqual(genesis, 'In the beginning God created the heavens and the earth.')
        self.assertEqual(matthew, 'This is the genealogy of Yeshua the Messiah, son of David, son of Avraham:')


class LxxGreekToHebrewIndexCommandTestCase(SimpleTestCase):
    def test_build_command_generates_ranked_candidates_from_tsv_evidence(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            evidence_path = temp_path / 'evidence.tsv'
            output_path = temp_path / 'lxx_greek_to_hebrew.json'
            evidence_path.write_text(
                '\n'.join([
                    'greek_strong\tgreek_lemma\thebrew_strong\thebrew_lemma\thebrew_transliteration\tcount',
                    'G3056\tλόγος\tH1697\tדבר\tdabar\t842',
                    'G3056\tλόγος\tH0565\tאמר\tamar\t103',
                    'G4102\tπίστις\tH0530\tאמונה\temunah\t25',
                    'G4102\tπίστις\tH0982\tבטח\tbatach\t8',
                ]) + '\n',
                encoding='utf-8',
            )

            call_command(
                'build_lxx_greek_to_hebrew_index',
                evidence_file=str(evidence_path),
                output=str(output_path),
            )

            payload = json.loads(output_path.read_text(encoding='utf-8'))
            self.assertIn('G3056', payload)
            self.assertEqual(payload['G3056']['greekLemma'], 'λόγος')
            self.assertEqual(payload['G3056']['hebrewCandidates'][0]['strong'], 'H1697')
            self.assertEqual(payload['G3056']['hebrewCandidates'][0]['count'], 842)
            self.assertEqual(payload['G3056']['hebrewCandidates'][0]['percentage'], 89.1)
            self.assertGreater(payload['G3056']['hebrewCandidates'][0]['confidence'], payload['G3056']['hebrewCandidates'][1]['confidence'])
            self.assertEqual(payload['G4102']['hebrewCandidates'][1]['transliteration'], 'batach')

    def test_build_command_falls_back_to_tbesg_lxx_notes_when_no_file_exists(self):
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            missing_path = temp_path / 'missing-evidence.tsv'
            output_path = temp_path / 'fallback-lxx-greek-to-hebrew.json'

            call_command(
                'build_lxx_greek_to_hebrew_index',
                evidence_file=str(missing_path),
                output=str(output_path),
                greek_strongs=['G0025'],
            )

            payload = json.loads(output_path.read_text(encoding='utf-8'))
            self.assertIn('G0025', payload)
            self.assertGreater(len(payload['G0025']['hebrewCandidates']), 0)
            self.assertTrue(payload['G0025']['hebrewCandidates'][0]['strong'].startswith('H'))


class DynamicUiRegressionTestCase(TestCase):
    def test_base_modal_renders_save_changes_button_alongside_auto_apply(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Save changes')

    def test_base_modal_defers_auto_apply_binding_until_dom_ready(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        # Function is defined in modal.html and called from base.html after jQuery loads
        self.assertContains(response, 'window.jcInitChangeLanguageModal')
        self.assertContains(response, 'jcInitChangeLanguageModal()')
        self.assertContains(response, 'changed.bs.select.jcAutoApply')

    def test_law_of_messiah_listing_renders_apply_filter_button(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="law-filter-apply-btn"')

    def test_law_of_messiah_listing_defers_filter_auto_apply_binding_until_dom_ready(self):
        response = self.client.get(reverse('commandments:law_of_messiah_listing'))

        self.assertEqual(response.status_code, 200)
        # Filter script is in extra_body_scripts (after jQuery), not block content
        self.assertContains(response, 'changed.bs.select.jcLawFilterAutoApply')
        # No DOMContentLoaded guard needed since script is after jQuery
        self.assertNotContains(response, 'initLawOfMessiahFilterAutoApply')


class MediaTemplateFilterTestCase(SimpleTestCase):
    def test_overview_media_badges_link_to_localized_detail_sections(self):
        badge_sections = {
            'movie': 'movies',
            'shortmovie': 'short_movies',
            'wajvideo': 'waj_video',
            'sermon': 'sermons',
            'podcast': 'podcasts',
            'testimony': 'testimonies',
            'blog': 'blogs',
            'book': 'books',
        }
        badges = [{'media_type': media_type, 'tooltip': media_type} for media_type in badge_sections]
        cards = (
            ('commandments/single_commandment_overview.html', 'commandment', 4, '/stap/4/'),
            ('law_of_messiah/single_law_of_messiah_overview.html', 'law', 'GA3', '/wet_van_christus/GA3/'),
        )
        with translation.override('nl'):
            for template, context_key, pk, path in cards:
                rendered = render_to_string(
                    template, {context_key: SimpleNamespace(id=pk, media_type_badge_list=badges)},
                )
                for section in badge_sections.values():
                    with self.subTest(path=path, section=section):
                        self.assertIn(f'href="{path}#{section}"', rendered)

    def test_commandment_sermon_badge_links_to_step_sermons_section(self):
        commandment = SimpleNamespace(
            id=4,
            title='Step',
            background_drawing=SimpleNamespace(img_url=''),
            found_superbook=SimpleNamespace(title=''),
            found_henkieshow=SimpleNamespace(title=''),
            media_type_badge_list=[{'media_type': 'sermon', 'tooltip': 'Sermon found'}],
        )

        with translation.override('nl'):
            rendered = render_to_string(
                'commandments/single_commandment_overview.html',
                {'commandment': commandment},
            )
            step_url = reverse('commandments:detail', args=[4])

        self.assertIn(f'href="{step_url}#sermons"', rendered)
        self.assertIn('href="/stap/4/#sermons"', rendered)

    def test_smooth_scroll_only_intercepts_same_page_anchors(self):
        script = (Path(settings.BASE_DIR) / 'static/js/customjs.js').read_text()

        self.assertIn('this.origin === window.location.origin', script)
        self.assertIn('this.pathname === window.location.pathname', script)
        self.assertIn('this.search === window.location.search', script)

    def test_is_youtube_url_filter_only_accepts_youtube_hosts(self):
        self.assertTrue(is_youtube_url_filter('https://www.youtube.com/watch?v=Ilbh6Dv_8Yw'))
        self.assertTrue(is_youtube_url_filter('https://youtu.be/Ilbh6Dv_8Yw'))
        self.assertFalse(is_youtube_url_filter('https://example.org/podcast'))
        self.assertFalse(is_youtube_url_filter('https://youtube.com.example.org/podcast'))

    def test_youtube_captions_url_converts_watch_url_to_embed(self):
        rendered = youtube_captions_url('https://www.youtube.com/watch?v=Ilbh6Dv_8Yw', 'nl')
        parsed = urlparse(rendered)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.netloc, 'www.youtube.com')
        self.assertEqual(parsed.path, '/embed/Ilbh6Dv_8Yw')
        self.assertEqual(query.get('cc_load_policy'), ['1'])
        self.assertEqual(query.get('cc_lang_pref'), ['nl'])

    def test_youtube_captions_url_keeps_embed_and_adds_captions(self):
        rendered = youtube_captions_url('https://www.youtube.com/embed/tLae0OzoF_w', 'en')
        parsed = urlparse(rendered)
        query = parse_qs(parsed.query)

        self.assertEqual(parsed.path, '/embed/tLae0OzoF_w')
        self.assertEqual(query.get('cc_load_policy'), ['1'])
        self.assertEqual(query.get('cc_lang_pref'), ['en'])


class MediaResourceAdminValidationTestCase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model().objects.create_user(
            username='media-admin',
            email='media-admin@example.com',
            password='secret',
            is_staff=True,
            is_superuser=True,
        )

    def _resource_form(self):
        request = self.factory.get('/')
        request.user = self.user
        request.session = self.client.session
        admin_instance = MediaResourceAdmin(MediaResource, admin.site)
        return admin_instance.get_form(request)

    def _resource_form_data(self, url):
        return {
            'law_of_messiah': '',
            'commandment': '',
            'lesson': '',
            'media_type': 'shortmovie',
            'title': 'Test video',
            'description': 'Test description',
            'img_url': '',
            'url': url,
            'author': 'Tester',
            'target_audience': 'any',
            'language': 'en',
            'is_public': 'on',
        }

    def test_media_resource_admin_form_blocks_unembeddable_youtube_video(self):
        FormClass = self._resource_form()
        with patch('walkasjesus_app.lib.youtube_embed_validation.requests.get', return_value=Mock(status_code=403)):
            form = FormClass(data=self._resource_form_data('https://www.youtube.com/watch?v=Ilbh6Dv_8Yw'))
            is_valid = form.is_valid()

        self.assertFalse(is_valid)
        self.assertIn('cannot be embedded', str(form.errors.get('url', '')))

    def test_media_resource_admin_form_accepts_and_normalizes_embeddable_youtube_video(self):
        FormClass = self._resource_form()
        with patch('walkasjesus_app.lib.youtube_embed_validation.requests.get', return_value=Mock(status_code=200)):
            form = FormClass(data=self._resource_form_data('https://www.youtube.com/watch?v=Ilbh6Dv_8Yw'))
            is_valid = form.is_valid()

        self.assertTrue(is_valid, form.errors)
        self.assertEqual(form.cleaned_data['url'], 'https://www.youtube.com/embed/Ilbh6Dv_8Yw')

    def test_media_resource_admin_form_auto_populates_1_to_1_counterparts(self):
        step = Commandment.objects.create(id=101, title='Test Step 101')
        law = LawOfMessiah.objects.create(id='L101', title='Test Law 101')
        law.related_steps.add(step)
        lesson = Lesson.objects.create(id=101, title='Test Lesson 101', commandment=step)

        FormClass = self._resource_form()

        # 1. Given commandment only -> auto-populates law_of_messiah and lesson
        data = self._resource_form_data('')
        data['commandment'] = str(step.id)
        form = FormClass(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get('law_of_messiah'), law)
        self.assertEqual(form.cleaned_data.get('lesson'), lesson)

        # 2. Given law_of_messiah only -> auto-populates commandment and lesson
        data = self._resource_form_data('')
        data['law_of_messiah'] = law.id
        form = FormClass(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get('commandment'), step)
        self.assertEqual(form.cleaned_data.get('lesson'), lesson)

        # 3. Given lesson only -> auto-populates commandment and law_of_messiah
        data = self._resource_form_data('')
        data['lesson'] = str(lesson.id)
        form = FormClass(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data.get('commandment'), step)
        self.assertEqual(form.cleaned_data.get('law_of_messiah'), law)

    def test_media_resource_admin_does_not_auto_populate_when_not_1_to_1(self):
        step = Commandment.objects.create(id=102, title='Test Step 102')
        law1 = LawOfMessiah.objects.create(id='L102A', title='Test Law 102A')
        law2 = LawOfMessiah.objects.create(id='L102B', title='Test Law 102B')
        law1.related_steps.add(step)
        law2.related_steps.add(step)

        FormClass = self._resource_form()
        data = self._resource_form_data('')
        data['commandment'] = str(step.id)
        form = FormClass(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        # Should not auto-populate law_of_messiah since there are 2 matches
        self.assertIsNone(form.cleaned_data.get('law_of_messiah'))

    def test_media_resource_related_targets_ajax_endpoint(self):
        step = Commandment.objects.create(id=103, title='Test Step 103')
        law = LawOfMessiah.objects.create(id='L103', title='Test Law 103')
        law.related_steps.add(step)
        lesson = Lesson.objects.create(id=103, title='Test Lesson 103', commandment=step)

        self.client.force_login(self.user)
        url = reverse('admin:commandments_app_mediaresource_related_targets')

        # Query by commandment
        resp = self.client.get(url, {'commandment': str(step.id)})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('commandment', {}).get('id'), str(step.id))
        self.assertEqual(data.get('law_of_messiah', {}).get('id'), law.id)
        self.assertEqual(data.get('lesson', {}).get('id'), str(lesson.id))

        # Query by law_of_messiah
        resp = self.client.get(url, {'law_of_messiah': law.id})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('commandment', {}).get('id'), str(step.id))
        self.assertEqual(data.get('lesson', {}).get('id'), str(lesson.id))

        # Query by lesson
        resp = self.client.get(url, {'lesson': str(lesson.id)})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get('commandment', {}).get('id'), str(step.id))
        self.assertEqual(data.get('law_of_messiah', {}).get('id'), law.id)


class MediaResourceCacheInvalidationTestCase(TestCase):
    def setUp(self):
        self.commandment = Commandment.objects.create(
            id=2026,
            title='Cache refresh test',
            title_negative='Cache refresh test negative',
        )

    def test_media_save_bumps_cache_version_and_normalizes_youtube_url(self):
        cache.set(MEDIA_CACHE_VERSION_KEY, 1)
        before = get_media_cache_version()

        resource = MediaResource.objects.create(
            commandment=self.commandment,
            media_type='shortmovie',
            title='New resource',
            author='Tester',
            url='https://youtu.be/Ilbh6Dv_8Yw',
            is_public=True,
        )
        resource.refresh_from_db()
        after = get_media_cache_version()

        self.assertGreater(after, before)
        self.assertEqual(resource.url, 'https://www.youtube.com/embed/Ilbh6Dv_8Yw')

    def test_media_delete_bumps_cache_version(self):
        resource = MediaResource.objects.create(
            commandment=self.commandment,
            media_type='shortmovie',
            title='Delete resource',
            author='Tester',
            url='https://example.org/video',
            is_public=True,
        )
        cache.set(MEDIA_CACHE_VERSION_KEY, 5)
        before = get_media_cache_version()

        resource.delete()
        after = get_media_cache_version()

        self.assertGreater(after, before)


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

    def test_collect_shared_media_omits_private_items(self):
        LawOfMessiahDrawing.objects.create(
            commandment=self.commandment,
            media_type=LawOfMessiahDrawing.MEDIA_TYPE_SONG,
            title='Private song',
            author='Unknown',
            url='https://example.org/private-song',
            target_audience='any',
            language='en',
            is_public=False,
        )

        grouped = _collect_shared_media_by_type(commandment=self.commandment, lesson=self.lesson)
        songs = grouped[LawOfMessiahDrawing.MEDIA_TYPE_SONG]

        self.assertEqual(songs, [])

    def test_podcast_media_is_collected_and_shown_as_a_badge(self):
        podcast = LawOfMessiahDrawing.objects.create(
            commandment=self.commandment,
            media_type=LawOfMessiahDrawing.MEDIA_TYPE_PODCAST,
            title='Podcast episode',
            author='Podcast host',
            url='https://example.org/podcast',
            target_audience='any',
            language='en',
            is_public=True,
        )

        grouped = _collect_shared_media_by_type(commandment=self.commandment)
        badges = self.commandment.media_type_badges()
        rendered_badges = render_to_string(
            'commandments/_media_type_badges.html',
            {'media_type_badges': badges},
        )

        self.assertIn(podcast, grouped[LawOfMessiahDrawing.MEDIA_TYPE_PODCAST])
        self.assertEqual(
            [badge['media_type'] for badge in badges],
            [LawOfMessiahDrawing.MEDIA_TYPE_PODCAST],
        )
        self.assertIn('/static/images/podcast.png', rendered_badges)

        law = LawOfMessiah.objects.create(id='LPOD', title='Podcast law')
        LawOfMessiahDrawing.objects.create(
            law_of_messiah=law,
            media_type=LawOfMessiahDrawing.MEDIA_TYPE_PODCAST,
            title='Law podcast',
            url='https://example.org/law-podcast',
            is_public=True,
        )
        self.assertEqual(
            [badge['media_type'] for badge in law.media_type_badges()],
            [LawOfMessiahDrawing.MEDIA_TYPE_PODCAST],
        )

    def test_podcast_from_legacy_lesson_import_is_saved_as_shared_media(self):
        podcast = SimpleNamespace(
            type='podcast',
            title='Lesson podcast',
            description='Podcast description',
            target_audience='any',
            language='en',
            img_url='',
            url='https://example.org/lesson-podcast',
            author='Podcast host',
            is_public=True,
        )

        ImportLessonMediaCommand()._add_media(self.lesson.id, podcast)

        self.assertTrue(
            LawOfMessiahDrawing.objects.filter(
                lesson=self.lesson,
                media_type=LawOfMessiahDrawing.MEDIA_TYPE_PODCAST,
                title=podcast.title,
            ).exists()
        )


class KidsOnlyMediaServerRenderingTestCase(TestCase):
    """Kids-only media (any media_type, not just superbook/henkieshow) must never be
    present in the server-rendered HTML unless the jc_kids_mode cookie is set, so it
    doesn't leak to non-JS clients such as curl or search engine crawlers."""

    def setUp(self):
        self.commandment = Commandment.objects.create(
            id=1002,
            title='Step 1002',
            title_negative='Step 1002 negative',
        )
        LawOfMessiahDrawing.objects.create(
            commandment=self.commandment,
            media_type=LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE,
            title='Kids only shortmovie',
            author='Someone',
            url='https://example.org/kids-shortmovie',
            target_audience='kids',
            language='en',
            is_public=True,
        )
        LawOfMessiahDrawing.objects.create(
            commandment=self.commandment,
            media_type=LawOfMessiahDrawing.MEDIA_TYPE_SONG,
            title='Adults song',
            author='Someone else',
            url='https://example.org/adults-song',
            target_audience='adults',
            language='en',
            is_public=True,
        )

    def test_kids_only_media_hidden_without_kids_mode_cookie(self):
        response = self.client.get(reverse('commandments:detail', args=[self.commandment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'targetaudience="kids"')
        self.assertContains(response, 'targetaudience="adults"')

    def test_kids_only_media_shown_with_kids_mode_cookie(self):
        self.client.cookies['jc_kids_mode'] = 'true'
        response = self.client.get(reverse('commandments:detail', args=[self.commandment.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'targetaudience="kids"')


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
        mock_bible_translation.return_value.all_in_supported_languages.return_value = [
            SimpleNamespace(id='de4e12af7f28f599-01', name='KJV', language='en'),
            SimpleNamespace(id='jnt-stern-en', name='Complete Jewish Bible (David H. Stern)', language='en'),
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
    def test_shows_cjb_for_any_authenticated_user_when_login_required(self, mock_bible_translation):
        mock_bible_translation.return_value.all_in_supported_languages.return_value = [
            SimpleNamespace(id='de4e12af7f28f599-01', name='KJV', language='en'),
            SimpleNamespace(id='jnt-stern-en', name='Complete Jewish Bible (David H. Stern)', language='en'),
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
        self.assertEqual(returned_ids, ['jnt-stern-en', 'de4e12af7f28f599-01'])
        self.assertEqual(payload['default_bible_id'], 'jnt-stern-en')


class BibleStudySharedPanelsTestCase(SimpleTestCase):
    def test_occurrence_options_keep_text_only_controls_out_of_the_dictionary_dialog(self):
        with translation.override('nl'):
            text_options = render_to_string('bible_study/_search_options.html', {
                'modal_id': 'bsWordSearchAdvancedModal', 'search_prefix': 'bs-search',
                'strong_search': False,
            })
            occurrence_options = render_to_string('bible_study/_search_options.html', {
                'modal_id': 'bsDictionarySearchAdvancedModal', 'search_prefix': 'bs-dictionary-search',
                'strong_search': True,
            })
        self.assertIn('id="bs-search-fuzziness"', text_options)
        self.assertIn('id="bs-search-exact-phrase"', text_options)
        self.assertIn('value="relevance"', text_options)
        self.assertNotIn('-fuzziness', occurrence_options)
        self.assertNotIn('-exact-phrase', occurrence_options)
        self.assertNotIn('value="relevance"', occurrence_options)
        self.assertIn('id="bs-dictionary-search-scope"', occurrence_options)
        self.assertIn('id="bs-dictionary-search-limit"', occurrence_options)
        self.assertIn('value="reverse-canonical"', occurrence_options)
        self.assertIn('Opslaan en zoeken', text_options)
        self.assertIn('Opslaan en zoeken', occurrence_options)

    def test_origin_explanations_are_translated_without_analysis_markers(self):
        with translation.override('nl'):
            script = render_to_string('bible_study/_study_panels_script.html')
        self.assertNotIn('bs-hebrew-part-overlap', script)
        self.assertNotIn('bs-hebrew-analysis-uncertain', script)
        self.assertNotIn('De onderstreepte letter kan zowel bij de woordstam', script)
        self.assertNotIn('mogelijk onvolledige analyse', script)
        self.assertIn('Afgeleid uit grammatica en woordvorm.', script)
        self.assertNotIn('Door STEPBible gemarkeerd onderdeel', script)
        self.assertNotIn('STEPBible-tagged component; role and boundaries', script)
        self.assertNotIn('Lemma uit het woordenboek van STEPBible', script)
        self.assertNotIn('STEPBible lexicon lemma.', script)
        self.assertIn('Sof pasoek: sluit een vers af', script)
        self.assertIn('Maqqef: verbindt woorden', script)
        self.assertIn('Paseq: scheidt woorden', script)
        self.assertIn('Mogelijke betekenissen (afhankelijk van de context)', script)
        self.assertIn('component.possible_meanings', script)

    def test_shared_original_renderer_and_preview_compile_and_render(self):
        script = render_to_string('bible_study/_study_panels_script.html')
        preview = render_to_string('bible_study/_study_reference_preview.html')
        self.assertEqual(script.count('function renderOriginalWordDetail('), 1)
        self.assertIn('hebrewWordStudyHtml(selectedWord)', script)
        self.assertIn('bs-search-parts-close', script)
        self.assertIn('bs-search-candidate-disclosure', script)
        self.assertIn('if (directGloss && !isHebrew && !searchDetails)', script)
        self.assertIn('if (selectedWord.grammar && !isHebrew && !searchDetails)', script)
        self.assertNotIn(".data('word-index') || ''", script)
        self.assertIn('renderOriginalWordDetail($target, payload, 0, true)', script)
        self.assertIn('bibleStudyLocalUsageHtml(candidate', script)
        self.assertIn("$root.find('.bible-study-original-shell", script)
        self.assertIn('fetchNext(nextVerse)', script)
        self.assertIn('waj-reference-preview-template', preview)
        self.assertIn('bs-occurrences-chunks', preview)

    def test_all_page_templates_load_the_shared_panels_through_base(self):
        base = get_template('base.html').template.source
        self.assertEqual(base.count('include "bible_study/_study_panels_script.html"'), 1)
        self.assertEqual(base.count('include "bible_study/_study_reference_preview.html"'), 1)
        for name in (
            'bible_study/bible_study.html',
            'maimonides/listing.html',
            'commandments/detail.html',
            'law_of_messiah/detail.html',
            'lessons/detail.html',
        ):
            with self.subTest(template=name):
                source = get_template(name).template.source
                self.assertIn('{% extends "base.html" %}', source)

    def test_page_scripts_do_not_keep_a_second_original_renderer(self):
        page_script = get_template('bible_study/_bible_study_script.html').template.source
        detail_script = (Path(settings.BASE_DIR) / 'static/js/customjs.js').read_text()
        self.assertIn('window.WAJBibleStudyPanels.create', page_script)
        self.assertIn('window.WAJBibleStudyPanels.create', detail_script)
        self.assertNotIn('function renderOriginalWordDetail', page_script)
        self.assertNotIn('bs-search-occurrences-btn', page_script)
        self.assertNotIn('bs-search-occurrence-detail-btn', page_script)
        self.assertNotIn('Word form in the matched verse', page_script)
        self.assertNotIn('escapeHtml(candidate.transliteration', page_script)
        self.assertIn('escapeHtml(occurrence ? occurrence.text', page_script)
        self.assertIn('bsWordSelection[candidates[0].strongs_number] = true', page_script)
        self.assertIn('if (study.unaligned_results)', page_script)
        self.assertIn('Word-study results may be incomplete for this translation.', page_script)
        self.assertIn('Use the third search box', page_script)
        self.assertIn("bsActiveSearchMode === 'lexicon' ? '#bs-dictionary-search-input'", page_script)
        self.assertIn("bsActiveSearchMode = this.id === 'bs-dictionary-search-btn' ? 'lexicon' : 'text'", page_script)
        self.assertIn("bsActiveSearchMode = this.id === 'bs-dictionary-search-input' ? 'lexicon' : 'text'", page_script)
        self.assertIn("mode: 'text'", page_script)
        self.assertNotIn('bs-search-word-study-enabled', page_script)
        self.assertNotIn('bs-search-mode', page_script)
        self.assertIn("originalLanguage: bsDictionaryLanguage()", page_script)
        self.assertIn("hebrew && greek ? 'both'", page_script)
        self.assertIn("options.mode === 'lexicon' && !options.originalLanguage", page_script)
        self.assertNotIn("var dictionary = studyEnabled &&", page_script)
        self.assertNotIn('detailOriginalRenderWordDetail', detail_script)
        self.assertNotIn('detail-inline-original', detail_script)

    def test_dictionary_summary_shows_selected_codes_and_lemmas_beside_query(self):
        script = render_to_string('bible_study/_bible_study_script.html')
        self.assertIn("var selectedWordSummary = (payload.selected_strongs || []).map", script)
        self.assertIn('return item.strongs_number === code;', script)
        self.assertIn('escapeHtml(candidate.lemma)', script)
        self.assertIn("(selectedWordSummary ? ' - ' + selectedWordSummary : '')", script)
        self.assertIn("(payload.mode === 'strongs' ? '' : '<em>'", script)
        self.assertNotIn("escapeHtml((payload.selected_strongs || []).join(', '))", script)


class BibleStudyLanguageCoverageTestCase(SimpleTestCase):
    databases = {'default'}

    @patch('walkasjesus_app.context_processors.available_sword_commentators_json', return_value='[]')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_bible_study_page_renders_settings_and_results(self, mock_bible_translation, _mock_sword_commentators):
        english_bible = MockBibleStudyBible(
            'en-kjv',
            'King James Version',
            'en',
            {
                ('JohnFirstBook', 2, 3): 'That which we have seen and heard declare we unto you.',
                ('JohnFirstBook', 2, 4): 'And these things write we unto you, that your joy may be full.',
                ('JohnFirstBook', 2, 5): 'This then is the message which we have heard of him.',
                ('JohnFirstBook', 2, 6): 'If we say that we have fellowship with him, and walk in darkness.',
            },
            copyright='Public domain',
        )
        mock_bible_translation.return_value.all_in_supported_languages.return_value = [english_bible]
        mock_bible_translation.return_value.get.side_effect = lambda bible_id: english_bible if bible_id == english_bible.id else None

        with self.settings(
            DEFAULT_BIBLE_ANY_LANGUAGE='en-kjv',
            DEFAULT_BIBLE_PER_LANGUAGE={'en': 'en-kjv'},
            DISABLED_BIBLE_TRANSLATIONS=[],
            CJB_BIBLE_ENABLED=False,
            DISABLE_CACHE_FOR_DEBUG=True,
        ):
            response = self.client.get(reverse('commandments:bible_study'))
            dutch_response = self.client.get(reverse('commandments:bible_study'), HTTP_ACCEPT_LANGUAGE='nl', follow=True)

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('id="bibleStudyForm"', html)
        self.assertIn('id="bs-results-region"', html)
        self.assertNotIn('id="bs-search-original-language"', html)
        self.assertIn('id="bs-search-hebrew" checked', html)
        self.assertIn('id="bs-search-greek"', html)
        self.assertNotIn('id="bs-search-mode"', html)
        self.assertIn('Search words in Bible translation', html)
        self.assertIn('Search words in Strong', html)
        self.assertIn('id="bs-dictionary-search-input"', html)
        self.assertIn('id="bs-dictionary-search-btn"', html)
        self.assertIn('id="bs-passage-search-btn"', html)
        self.assertEqual(html.count('class="bs-word-search-panel bs-search-method-panel"'), 3)
        self.assertIn('Use the third search box', html)
        self.assertNotIn('id="bs-search-word-study-enabled"', html)
        self.assertNotIn('Include Hebrew/Greek word study', html)
        self.assertNotIn('data-search-mode=', html)
        self.assertEqual(html.count('data-target="#bsWordSearchAdvancedModal"'), 1)
        self.assertEqual(html.count('class="col-lg-4 mb-3"'), 3)
        self.assertIn('These options apply only to searching words in Bible verses.', html)
        self.assertIn('Select Hebrew, Greek or both before searching the dictionary.', html)
        self.assertNotIn('Search original-word meanings and Strong&#x27;s numbers, then select words', html)
        self.assertIn('Check Hebrew, Greek or both', html)
        self.assertIn('The second box searches only the first selected translation', html)
        self.assertIn('A word without a link was not reliably aligned', html)
        self.assertNotIn('You can also search for words or phrases in the first selected translation and jump straight', html)
        self.assertIn('King James Version', html)
        self.assertIn('That which we have seen and heard declare we unto you.', html)
        self.assertEqual(html.count('data-bs-nav="prev" data-step="5"'), 2)
        self.assertEqual(html.count('data-bs-nav="next" data-step="5"'), 2)
        dutch_html = dutch_response.content.decode('utf-8')
        self.assertIn('Zoek woorden in het Strong-woordenboek', dutch_html)
        self.assertIn('Bijbelvertaling 1', dutch_html)
        self.assertIn('Bijbelvertaling 2', dutch_html)
        self.assertIn('Hebreeuws', dutch_html)
        self.assertIn('/static/images/StepBible.png', html)
        self.assertIn('/static/images/BLB.png', html)
        self.assertIn('https://www.stepbible.org/?q=version=KJV@strong=', html)
        self.assertIn('class="jc-tooltip-host jc-tooltip-immediate"', html)
        self.assertIn('data-jc-tooltip=', html)
        self.assertEqual(html.count('function renderOriginalWordDetail('), 1)
        self.assertIn('window.WAJBibleStudyPanels.create', html)

    @patch('walkasjesus_app.views.user_preferences.BibleTranslation')
    def test_bible_translations_endpoint_returns_bibles_for_each_language(self, mock_bible_translation):
        mock_bible_translation.return_value.all_in_supported_languages.return_value = [
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
                ('en', ['en-kjv', 'en-nkjv', 'nl-hsv', 'nl-svv'], 'en-kjv'),
                ('nl', ['nl-hsv', 'nl-svv', 'en-kjv', 'en-nkjv'], 'nl-hsv'),
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

    @patch('walkasjesus_app.views.bible_study_view.requests.get')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_bible_study_search_endpoint_uses_api_bible_for_first_translation(self, mock_bible_translation, mock_requests_get):
        cache.clear()
        mock_bible_translation.return_value.get.return_value = SimpleNamespace(
            id='en-kjv',
            name='King James Version',
            language='en',
        )
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'data': {
                'total': 1,
                'verses': [
                    {
                        'id': 'REV.22.2',
                        'reference': 'Revelation 22:2',
                        'text': 'In the midst of the street of it, and on either side of the river, was there the tree of life.',
                    }
                ],
            }
        }
        mock_requests_get.return_value = mock_response

        with self.settings(DISABLED_BIBLE_TRANSLATIONS=[], CJB_BIBLE_ENABLED=False, BIBLE_API_KEY='test-key', DISABLE_CACHE_FOR_DEBUG=True):
            response = self.client.get(
                reverse('commandments:bible_study_search'),
                {'bible_id': 'en-kjv', 'query': 'Tree of life'},
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['query'], 'Tree of life')
        self.assertEqual(payload['bible_display_name'], 'EN - King James Version')
        self.assertEqual(payload['results'][0]['reference'], 'Revelation 22:2')
        called_url = mock_requests_get.call_args.args[0]
        self.assertIn('/v1/bibles/en-kjv/search?', called_url)
        called_params = parse_qs(urlparse(called_url).query)
        self.assertEqual(called_params['query'][0], 'Tree of life')
        self.assertEqual(called_params['limit'][0], '10')
        self.assertEqual(called_params['offset'][0], '0')
        self.assertEqual(called_params['sort'][0], 'canonical')
        self.assertEqual(called_params['fuzziness'][0], 'AUTO')
        self.assertEqual(mock_requests_get.call_args.kwargs['headers']['api-key'], 'test-key')

    @patch('walkasjesus_app.views.bible_study_view.requests.get')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_bible_study_search_endpoint_accepts_advanced_api_bible_options(self, mock_bible_translation, mock_requests_get):
        cache.clear()
        mock_bible_translation.return_value.get.return_value = SimpleNamespace(
            id='en-kjv',
            name='King James Version',
            language='en',
        )
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'data': {
                'total': 75,
                'verseCount': 64,
                'verses': [
                    {
                        'id': 'GEN.1.11',
                        'reference': 'Genesis 1:11',
                        'text': 'Let the earth bring forth grass, the herb yielding seed, and the fruit tree yielding fruit.',
                    }
                ],
            }
        }
        mock_requests_get.return_value = mock_response

        with self.settings(DISABLED_BIBLE_TRANSLATIONS=[], CJB_BIBLE_ENABLED=False, BIBLE_API_KEY='test-key', DISABLE_CACHE_FOR_DEBUG=True):
            response = self.client.get(
                reverse('commandments:bible_study_search'),
                {
                    'bible_id': 'en-kjv',
                    'query': 'tree',
                    'limit': '25',
                    'offset': '50',
                    'sort': 'canonical',
                    'fuzziness': '0',
                    'range': 'GEN.1.1-MAL.4.6',
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['limit'], 25)
        self.assertEqual(payload['offset'], 50)
        self.assertEqual(payload['sort'], 'canonical')
        self.assertEqual(payload['fuzziness'], '0')
        self.assertEqual(payload['range'], 'GEN.1.1-MAL.4.6')
        self.assertEqual(payload['page'], 3)
        self.assertEqual(payload['page_count'], 3)
        called_params = parse_qs(urlparse(mock_requests_get.call_args_list[0].args[0]).query)
        self.assertEqual(called_params['range'][0], 'GEN.1.1-MAL.4.6')
        self.assertEqual(called_params['offset'][0], '50')
        self.assertEqual(called_params['sort'][0], 'canonical')
        self.assertEqual(called_params['fuzziness'][0], '0')

    @patch('walkasjesus_app.views.bible_study_view.requests.get')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_bible_study_search_page_labels_use_bible_order(self, mock_bible_translation, mock_requests_get):
        cache.clear()
        mock_bible_translation.return_value.get.return_value = SimpleNamespace(
            id='en-kjv',
            name='King James Version',
            language='en',
        )
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            'data': {
                'total': 2,
                'verseCount': 2,
                'verses': [
                    {'id': 'EZK.31.9', 'reference': 'Ezekiel 31:9', 'text': 'tree'},
                    {'id': 'DEU.6.11', 'reference': 'Deuteronomy 6:11', 'text': 'tree'},
                ],
            }
        }
        mock_requests_get.return_value = mock_response

        with self.settings(DISABLED_BIBLE_TRANSLATIONS=[], CJB_BIBLE_ENABLED=False, BIBLE_API_KEY='test-key', DISABLE_CACHE_FOR_DEBUG=True):
            response = self.client.get(
                reverse('commandments:bible_study_search'),
                {'bible_id': 'en-kjv', 'query': 'tree', 'limit': '2'},
            )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['pages'][0]['range_label'], 'Deuteronomy 6:11–Ezekiel 31:9')


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

    @patch('walkasjesus_app.views.user_preferences.requests.get')
    @patch('walkasjesus_app.views.user_preferences.requests.post')
    def test_translation_provider_failure_returns_original_text(self, mock_requests_post, mock_requests_get):
        mock_requests_post.side_effect = RuntimeError('primary provider unavailable')
        mock_requests_get.side_effect = RuntimeError('fallback provider unavailable')

        self.assertEqual(
            _translate_commentary_text('In the beginning', 'nl'),
            'In the beginning',
        )

    @patch('walkasjesus_app.views.user_preferences._translate_google_batch')
    def test_translation_endpoint_supports_batch_texts(self, mock_translate_batch):
        cache.clear()
        mock_translate_batch.return_value = ['zaad', 'zaaien']

        response = self.client.post(
            reverse('commandments:commentary_translate'),
            {'texts': json.dumps(['seed', 'sowing']), 'target_language': 'nl'},
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode('utf-8'))
        self.assertEqual(payload['translations']['seed'], 'zaad')
        self.assertEqual(payload['translations']['sowing'], 'zaaien')
        mock_translate_batch.assert_called_once_with(['seed', 'sowing'], 'nl')


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
