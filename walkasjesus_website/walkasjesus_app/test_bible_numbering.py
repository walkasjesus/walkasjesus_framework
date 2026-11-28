import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.simple_cache import SimpleCache
from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from walkasjesus_app.lib.bible_numbering_checks import scan_numbering_cache
from walkasjesus_app.lib.bible_numbering_fetch import NumberingSourceFetcher
from walkasjesus_app.models.bible_numbering import BibleNumberingReview


def passage_entry(reference, content, expiry=None):
    return (
        f'https://api.scripture.api.bible/v1/bibles/test/passages/{reference}?content-type=text',
        {
            'expires_at': time.time() + 3600 if expiry is None else expiry,
            'value': json.dumps({'data': {'content': content}}),
        },
    )


class NumberingCacheTest(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'

    def write_cache(self, entries):
        self.path.write_text(json.dumps(entries), encoding='utf-8')

    def test_combined_markers_are_not_duplicates_and_report_has_no_text(self):
        self.write_cache(dict([passage_entry('TIT.1.1-TIT.1.5', '[1–4] Private text. [5] More.')]))
        original = self.path.read_bytes()
        with patch('requests.Session.get', side_effect=AssertionError('No network')):
            result = scan_numbering_cache(self.path)
        bible = result['bibles'][0]
        self.assertEqual(result['api_requests'], 0)
        self.assertEqual(bible['merged_groups'], ['TIT.1.1-4'])
        self.assertEqual(bible['available_references'], 5)
        self.assertEqual(bible['findings'], [])
        self.assertNotIn('Private text', json.dumps(result))
        self.assertEqual(self.path.read_bytes(), original)

    def test_expired_unknown_and_long_ttl_entries_are_not_examined(self):
        now = time.time()
        legacy_key, legacy = passage_entry('TIT.1.2-TIT.1.2', 'invalid')
        legacy.pop('expires_at')
        self.write_cache(dict([
            passage_entry('TIT.1.1-TIT.1.1', 'invalid', expiry=now - 1),
            (legacy_key, legacy),
            passage_entry('TIT.1.3-TIT.1.3', 'invalid', expiry=now + 180 * 86400),
        ]))
        report = scan_numbering_cache(self.path, now=now)['bibles'][0]
        self.assertEqual(report['entries'], {'expired': 1, 'unknown_expiry': 1, 'untrusted_ttl': 1})
        self.assertEqual(report['findings'], [])
        self.assertEqual(report['scopes']['structure']['state'], 'no_data')

    def test_missing_markers_and_conflicting_boundaries_are_reported(self):
        self.write_cache(dict([
            passage_entry('TIT.1.1-TIT.1.4', '[1-4] Combined.'),
            passage_entry('TIT.1.1-TIT.1.5', '[1] One. [2] Two. [3] Three. [4] Four.'),
        ]))
        findings = scan_numbering_cache(self.path)['bibles'][0]['findings']
        self.assertIn('missing_requested_verses', {item['kind'] for item in findings})
        self.assertEqual(sum(item['kind'] == 'conflicting_cached_boundaries' for item in findings), 4)

    def test_selected_books_use_generic_reference_mappings(self):
        self.write_cache(dict([
            passage_entry('NUM.26.1-NUM.26.1', '[1] Text.'),
            passage_entry('1CH.6.1-1CH.6.1', '[1] Text.'),
            passage_entry('MAL.4.1-MAL.4.1', '[1] Text.'),
        ]))
        scopes = scan_numbering_cache(
            self.path, books=['Numbers', 'ChroniclesFirstBook', 'Malachi', 'Titus'],
        )['bibles'][0]['scopes']
        for scope, reference in (
            ('numbers', 'NUM.25.19'), ('chroniclesfirstbook', '1CH.5.27'), ('malachi', 'MAL.3.19'),
        ):
            with self.subTest(scope=scope):
                self.assertIn(reference, scopes[scope]['cached_examples'])
                self.assertGreater(scopes[scope]['expected_cases'], 0)
        self.assertNotIn('joel', scopes)
        self.assertEqual(scopes['titus']['state'], 'no_reference_mapping')

    def test_offline_mode_blocks_startup_and_cache_misses_without_refresh_deletion(self):
        client = CachedBibleApiClient('test')
        client.cache = SimpleCache(Path(self.directory.name) / 'client.json')
        client.cache.set_value('cached', 'content')
        with patch.dict(os.environ, {'BIBLE_API_OFFLINE': '1'}), patch('requests.get') as network:
            self.assertEqual(client.get('cached'), 'content')
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                client.get('missing')
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                client.refresh('cached')
            self.assertEqual(client.cache.get_value('cached'), 'content')
            network.assert_not_called()
        self.write_cache(dict([passage_entry('TIT.1.1-TIT.1.1', '[1] Text.')]))
        code = (
            "import runpy,sys; from unittest.mock import patch; "
            f"sys.argv=['manage.py','check_bible_numbering','--cache-only','--no-save','--cache-path',{str(self.path)!r}]; "
            "\nwith patch('requests.sessions.Session.request',side_effect=AssertionError('Network forbidden')) as network:\n"
            " runpy.run_path('manage.py',run_name='__main__')\n"
            " network.assert_not_called()\n"
        )
        environment = os.environ.copy()
        environment.pop('BIBLE_API_OFFLINE', None)
        result = subprocess.run(
            [sys.executable, '-c', code], cwd=Path(__file__).resolve().parents[1], env=environment,
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('API requests: 0', result.stdout)


@override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'limited': 5})
class NumberingAcquisitionTest(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'
        self.path.write_text('{}', encoding='utf-8')
        self.fetcher = NumberingSourceFetcher(self.path, 'test-key', sleep_seconds=0)
        self.addCleanup(self.fetcher.close)
        self.fetched_urls = []

    def provider(self, url, **kwargs):
        self.fetched_urls.append(url)
        self.assertFalse(kwargs['allow_redirects'])
        if url.endswith('/books'):
            data = [{'id': 'JOL'}]
        elif url.endswith('/books/JOL/chapters'):
            data = [{'id': f'JOL.{chapter}'} for chapter in range(1, 5)]
        elif '/chapters/' in url:
            chapter = int(url.split('/chapters/JOL.')[1].split('/')[0])
            count = {2: 27, 3: 5, 4: 21}[chapter]
            data = [{'id': f'JOL.{chapter}.{verse}'} for verse in range(1, count + 1)]
        elif '/passages/' in url:
            reference = url.split('/passages/')[1].split('?')[0]
            first, last = reference.split('-')
            chapter, start = map(int, first.split('.')[1:])
            end = int(last.split('.')[-1])
            data = {'content': ' '.join(f'[{verse}] Test {chapter}:{verse}.' for verse in range(start, end + 1))}
        else:
            raise AssertionError(url)
        payload = {'data': data}
        return Mock(status_code=200, text=json.dumps(payload), json=Mock(return_value=payload))

    def test_source_fetch_bypasses_blocked_mapping_and_second_run_uses_cache(self):
        with patch.object(self.fetcher.session, 'get', side_effect=self.provider) as network, \
                patch('walkasjesus_app.views.bible_study_view._study_verse_references',
                      side_effect=AssertionError('Must not use study mapping')):
            result = self.fetcher.acquire(['test'], ['Joel'])
            self.assertFalse(result['errors'])
            self.assertEqual(result['requests'], 7)
            self.assertEqual(network.call_count, 7)
            self.assertTrue(any('/passages/JOL.3.1-JOL.3.5?' in url for url in self.fetched_urls))
            self.assertTrue(any('/passages/JOL.4.1-JOL.4.21?' in url for url in self.fetched_urls))
        report = scan_numbering_cache(self.path)['bibles'][0]
        self.assertEqual(report['scopes']['joel']['cached_candidates'], 26)
        second = NumberingSourceFetcher(self.path, 'test-key', sleep_seconds=0)
        try:
            with patch.object(second.session, 'get', side_effect=AssertionError('No repeated fetch')):
                self.assertEqual(second.acquire(['test'], ['Joel'])['requests'], 0)
        finally:
            second.close()

    def test_budget_counts_metadata_and_resumes_without_refetch(self):
        self.fetcher.max_requests = 3
        with patch.object(self.fetcher.session, 'get', side_effect=self.provider) as network:
            result = self.fetcher.acquire(['test'], ['Joel'])
        self.assertEqual(network.call_count, 3)
        self.assertTrue(result['budget_exhausted'])
        second = NumberingSourceFetcher(self.path, 'test-key', max_requests=3, sleep_seconds=0)
        try:
            with patch.object(second.session, 'get', side_effect=self.provider) as network:
                result = second.acquire(['test'], ['Joel'])
            self.assertEqual(network.call_count, 3)
            self.assertTrue(result['budget_exhausted'])
        finally:
            second.close()

    def test_numbers_acquires_only_risk_verses_within_budget(self):
        def provider(url, **kwargs):
            if url.endswith('/books'):
                data = [{'id': 'NUM'}]
            elif url.endswith('/books/NUM/chapters'):
                data = [{'id': 'NUM.25'}, {'id': 'NUM.26'}]
            elif url.endswith('/chapters/NUM.25/verses'):
                data = [{'id': f'NUM.25.{verse}'} for verse in range(1, 19)]
            elif url.endswith('/chapters/NUM.26/verses'):
                data = [{'id': f'NUM.26.{verse}'} for verse in range(1, 66)]
            elif url.endswith('/passages/NUM.26.1-NUM.26.1?content-type=text'):
                data = {'content': '[1] Text.'}
            else:
                raise AssertionError(url)
            payload = {'data': data}
            return Mock(status_code=200, text=json.dumps(payload), json=Mock(return_value=payload))

        self.fetcher.max_requests = 5
        with patch.object(self.fetcher.session, 'get', side_effect=provider) as network:
            result = self.fetcher.acquire(['test'], ['Numbers'])
        self.assertFalse(result['errors'])
        self.assertEqual(result['requests'], 5)
        self.assertEqual(network.call_count, 5)
        scopes = scan_numbering_cache(self.path, books=['Numbers'])['bibles'][0]['scopes']
        self.assertIn('NUM.25.19', scopes['numbers']['cached_examples'])

    def test_book_without_reference_mapping_does_not_fetch_metadata(self):
        with patch.object(self.fetcher.session, 'get', side_effect=AssertionError('No network')) as network:
            result = self.fetcher.acquire(['test'], ['Titus'])
        self.assertEqual(result['requests'], 0)
        network.assert_not_called()

    def test_one_hundred_request_ceiling_is_not_exceeded_across_translations(self):
        with patch.object(self.fetcher.session, 'get', side_effect=self.provider) as network:
            result = self.fetcher.acquire([f'test{index}' for index in range(16)], ['Joel'])
        self.assertEqual(result['requests'], 100)
        self.assertEqual(network.call_count, 100)
        self.assertTrue(result['budget_exhausted'])

    def test_rate_limit_stops_acquisition_without_retries(self):
        with patch.object(self.fetcher.session, 'get', return_value=Mock(status_code=429)) as network:
            result = self.fetcher.acquire(['test', 'test2'], ['Joel'])
        self.assertEqual(result['requests'], 1)
        self.assertEqual(network.call_count, 1)
        self.assertTrue(result['errors'])

    def test_restricted_translation_never_prefetched_and_failures_count(self):
        with patch.object(self.fetcher.session, 'get') as network:
            result = self.fetcher.acquire(['limited'], ['Joel'])
        self.assertEqual(result['requests'], 0)
        self.assertTrue(result['skipped'])
        network.assert_not_called()
        self.fetcher.max_requests = 1
        with patch.object(self.fetcher.session, 'get', side_effect=requests.Timeout()) as network:
            result = self.fetcher.acquire(['test'], ['Joel'])
        self.assertEqual(result['requests'], 1)
        self.assertTrue(result['errors'])
        self.assertEqual(json.loads(self.path.read_text()), {})


class NumberingReportTest(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'
        self.path.write_text(json.dumps(dict([
            passage_entry('TIT.1.1-TIT.1.1', '[1] Text.'),
        ])), encoding='utf-8')

    def test_cache_only_saves_report_without_manual_checklist(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
            call_command('check_bible_numbering', cache_path=self.path, cache_only=True, stdout=io.StringIO())
        review = BibleNumberingReview.objects.get(bible_id='test')
        self.assertFalse(hasattr(review, 'checks'))
        self.assertEqual(review.report['acquisition']['requests'], 0)
        self.assertTrue(review.report['scopes'])

    def test_output_shows_translation_name_without_network_lookup(self):
        for bibles, expected in (
            ([SimpleNamespace(id='test', name='Naardense Bijbel 2024')], 'Naardense Bijbel 2024'),
            ([], 'name unavailable in cached catalogue'),
        ):
            with self.subTest(expected=expected):
                output = io.StringIO()
                with patch('walkasjesus_app.management.commands.check_bible_numbering.BibleTranslation') as translations, \
                        patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
                    translations.return_value.all.return_value = bibles
                    call_command(
                        'check_bible_numbering', cache_path=self.path, cache_only=True,
                        no_save=True, stdout=output,
                    )
                self.assertIn(f'test ({expected}): fresh=1', output.getvalue())
                self.assertIn('API requests: 0/100', output.getvalue())

    def test_invalid_budget_and_output_cannot_modify_cache(self):
        original = self.path.read_bytes()
        for budget in (-1, 101):
            with self.assertRaises(CommandError):
                call_command('check_bible_numbering', cache_path=self.path, max_requests=budget, stdout=io.StringIO())
        with self.assertRaisesRegex(CommandError, 'must not overwrite'):
            call_command('check_bible_numbering', cache_path=self.path, output=self.path, stdout=io.StringIO())
        self.assertEqual(self.path.read_bytes(), original)
        call_command('check_bible_numbering', cache_path=self.path, cache_only=True, no_save=True, stdout=io.StringIO())
        self.assertFalse(BibleNumberingReview.objects.exists())

    def test_language_filters_output_storage_and_acquisition(self):
        entries = dict([passage_entry('TIT.1.1-TIT.1.1', '[1] Text.')])
        entries.update({key.replace('/test/', '/english/'): value for key, value in list(entries.items())})
        self.path.write_text(json.dumps(entries), encoding='utf-8')
        output = io.StringIO()
        with patch('walkasjesus_app.management.commands.check_bible_numbering.BibleTranslation') as translations, \
                patch('walkasjesus_app.management.commands.check_bible_numbering.NumberingSourceFetcher') as fetchers:
            translations.return_value.all.return_value = [
                SimpleNamespace(id='test', name='Nederlandse vertaling', language='nl'),
                SimpleNamespace(id='english', name='English translation', language='en'),
            ]
            fetchers.return_value.acquire.return_value = {
                'requests': 0, 'budget_exhausted': False, 'errors': [], 'skipped': [],
            }
            call_command('check_bible_numbering', cache_path=self.path, language='NL', stdout=output)
            self.assertEqual(fetchers.return_value.acquire.call_args.args[0], ['test'])
            self.assertIn('test (Nederlandse vertaling)', output.getvalue())
            self.assertNotIn('english (English translation)', output.getvalue())
            self.assertEqual(list(BibleNumberingReview.objects.values_list('bible_id', flat=True)), ['test'])

            fetchers.reset_mock()
            output = io.StringIO()
            call_command(
                'check_bible_numbering', cache_path=self.path, language='nl',
                bible_ids=['english'], stdout=output, stderr=io.StringIO(),
            )
            fetchers.assert_not_called()
            self.assertNotIn('english (English translation)', output.getvalue())
            self.assertNotIn('test (Nederlandse vertaling)', output.getvalue())

    def test_unknown_language_fails_without_api_lookup(self):
        with patch('walkasjesus_app.management.commands.check_bible_numbering.BibleTranslation') as translations, \
                patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
            translations.return_value.all.return_value = []
            with self.assertRaisesRegex(CommandError, 'cached Bible catalogue'):
                call_command('check_bible_numbering', cache_path=self.path, language='nl', stdout=io.StringIO())

    def test_books_are_normalized_for_acquisition_output_and_saved_report(self):
        output = io.StringIO()
        with patch('walkasjesus_app.management.commands.check_bible_numbering.NumberingSourceFetcher') as fetchers:
            fetchers.return_value.acquire.return_value = {
                'requests': 0, 'budget_exhausted': False, 'errors': [], 'skipped': [],
            }
            call_command(
                'check_bible_numbering', cache_path=self.path, books=['NuMbErS', 'numbers'], stdout=output,
            )
            self.assertEqual(fetchers.return_value.acquire.call_args.args[1], ['Numbers'])
        self.assertIn('  numbers:', output.getvalue())
        self.assertNotIn('  joel:', output.getvalue())
        self.assertEqual(
            set(BibleNumberingReview.objects.get(bible_id='test').report['scopes']),
            {'numbers', 'structure', 'merged'},
        )

    def test_all_books_includes_other_numbering_risks_without_network(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
            call_command(
                'check_bible_numbering', '--books=ALL', cache_path=self.path,
                cache_only=True, stdout=io.StringIO(),
            )
        scopes = BibleNumberingReview.objects.get(bible_id='test').report['scopes']
        for scope in ('numbers', 'chroniclesfirstbook', 'malachi', 'psalms', 'hosea', 'joel'):
            self.assertGreater(scopes[scope]['expected_cases'], 0)
        self.assertEqual(scopes['titus']['state'], 'no_reference_mapping')

    def test_unknown_book_fails_before_acquisition_or_report_writes(self):
        with patch('requests.sessions.Session.request', side_effect=AssertionError('No network')):
            with self.assertRaisesRegex(CommandError, 'Unknown Bible book'):
                call_command(
                    'check_bible_numbering', '--books=nubmers', cache_path=self.path, stdout=io.StringIO(),
                )
        self.assertFalse(BibleNumberingReview.objects.exists())

    def test_admin_is_report_only_and_anonymous_access_is_blocked(self):
        review = BibleNumberingReview.objects.create(bible_id='test', report={'findings': [], 'scopes': {}})
        url = reverse('admin:commandments_app_biblenumberingreview_change', args=[review.pk])
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_superuser(username='report-viewer', password='test-password')
        self.client.force_login(user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="checks-TOTAL_FORMS"')
        self.assertEqual(self.client.post(url, {'notes': 'change', '_save': 'Save'}).status_code, 403)
