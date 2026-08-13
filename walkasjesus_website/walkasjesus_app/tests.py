import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.cache import cache
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from walkasjesus_app.admin import MediaResourceAdmin
from walkasjesus_app.models import AbstractBibleReference, DirectBibleReference, Commandment, Lesson, LawOfMessiahDrawing
from walkasjesus_app.models import PrimaryBibleReference, BibleBooks
from walkasjesus_app.models.bibles import BibleTranslationMetaData, BibleTranslation, LocalCompleteJewishBible
from walkasjesus_app.models.sword_commentary import SwordCommentaryEntry, SwordCommentarySource
from walkasjesus_app.models.bible_usage import BibleTranslationUsageDaily, PageVisitDaily
from walkasjesus_app.models.law_of_messiah_media import MediaResource
from walkasjesus_app.models.media_review import MediaReviewRequest
from walkasjesus_app.lib.bible_api_rate_limit import BibleApiRateLimitExceeded, consume_bible_api_quota
from walkasjesus_app.lib.strongs_service import _candidate_payload, original_text_payload
from walkasjesus_app.context_processors import cache_settings
from walkasjesus_app.lib.media_cache_version import MEDIA_CACHE_VERSION_KEY, get_media_cache_version
from walkasjesus_app.templatetags.media_extras import youtube_captions_url
from walkasjesus_app.views.admin.admin_bible_usage_view import AdminBibleUsageView
from walkasjesus_app.views.admin.admin_page_usage_view import AdminPageUsageView
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


class StrongsServiceFallbackTestCase(TestCase):
    def test_original_text_payload_uses_non_clickable_fallback_for_missing_stepbible_rows(self):
        payload = original_text_payload('Psalms', 3, 2)

        self.assertGreater(len(payload['words']), 0)
        self.assertTrue(all(not word['clickable'] for word in payload['words']))
        self.assertTrue(all(not word['has_candidates'] for word in payload['words']))
        self.assertTrue(all(not word['detail_note'] for word in payload['words']))

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
        self.assertEqual(candidate['usage_outline'][0]['count'], 0)
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
        self.assertEqual(execute['count'], 0)
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
        mock_bible_translation.return_value.all_enabled.return_value = [
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
        mock_bible_translation.return_value.all_enabled.return_value = [
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
        self.assertEqual(returned_ids, ['de4e12af7f28f599-01', 'jnt-stern-en'])
        self.assertEqual(payload['default_bible_id'], 'jnt-stern-en')


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

        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('id="bibleStudyForm"', html)
        self.assertIn('id="bs-results-region"', html)
        self.assertIn('King James Version', html)
        self.assertIn('That which we have seen and heard declare we unto you.', html)

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
