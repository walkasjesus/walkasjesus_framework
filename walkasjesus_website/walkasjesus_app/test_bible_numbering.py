import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.simple_cache import SimpleCache
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from walkasjesus_app.lib.bible_numbering_checks import scan_numbering_cache, numbering_mapping_revision
from walkasjesus_app.lib.bible_numbering_review import check_needs_revalidation
from walkasjesus_app.models.bible_numbering import (
    BibleNumberingCheck, BibleNumberingReview, ensure_numbering_checklist,
)


def passage_entry(reference, content, expiry=None):
    key = f'https://api.scripture.api.bible/v1/bibles/test/passages/{reference}?content-type=text'
    return key, {
        'expires_at': time.time() + 3600 if expiry is None else expiry,
        'value': json.dumps({'data': {'content': content}}),
    }


class CacheOnlyNumberingTest(SimpleTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'

    def write_cache(self, entries):
        self.path.write_text(json.dumps(entries), encoding='utf-8')

    def test_combined_markers_are_not_duplicates_and_text_is_not_in_report(self):
        self.write_cache(dict([passage_entry('TIT.1.1-TIT.1.5', '[1–4] Synthetic private text. [5] More text.')]))
        original = self.path.read_bytes()
        with patch('requests.get', side_effect=AssertionError('Network access forbidden')):
            result = scan_numbering_cache(self.path)
        bible = result['bibles'][0]
        self.assertEqual(result['api_requests'], 0)
        self.assertEqual(bible['merged_groups'], ['TIT.1.1-4'])
        self.assertEqual(bible['available_references'], 5)
        self.assertEqual(bible['findings'], [])
        self.assertEqual(bible['scopes']['psalms']['state'], 'incomplete')
        self.assertNotIn('Synthetic private text', json.dumps(result))
        self.assertEqual(self.path.read_bytes(), original)

    def test_expired_legacy_and_long_ttl_entries_are_not_examined(self):
        now = time.time()
        legacy_key, legacy = passage_entry('TIT.1.2-TIT.1.2', 'invalid')
        legacy.pop('expires_at')
        self.write_cache(dict([
            passage_entry('TIT.1.1-TIT.1.1', 'not JSON verse content', expiry=now - 1),
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

    def test_fresh_nt_only_catalogue_does_not_require_ot_checks(self):
        catalogue = 'https://api.scripture.api.bible/v1/bibles/test/books'
        self.write_cache(dict([
            passage_entry('TIT.1.1-TIT.1.1', '[1] Text.'),
            (catalogue, {'expires_at': time.time() + 3600, 'value': json.dumps({'data': [{'id': 'TIT'}]})}),
        ]))
        scopes = scan_numbering_cache(self.path)['bibles'][0]['scopes']
        self.assertEqual(scopes['hosea']['state'], 'not_applicable')
        self.assertEqual(scopes['joel']['expected_cases'], 0)

    def test_chapter_catalogue_coverage_and_empty_text_are_not_false_successes(self):
        catalogue = 'https://api.scripture.api.bible/v1/bibles/test/books/TIT/chapters'
        self.write_cache(dict([
            passage_entry('TIT.1.1-TIT.1.2', '[1] [2] Text.'),
            passage_entry('TIT.4.1-TIT.4.1', '[1] Text.'),
            (catalogue, {
                'expires_at': time.time() + 3600,
                'value': json.dumps({'data': [{'id': f'TIT.{chapter}'} for chapter in (1, 2, 3)]}),
            }),
        ]))
        result = scan_numbering_cache(self.path)['bibles'][0]
        self.assertEqual(result['chapter_catalogue_coverage'], [
            {'book': 'TIT', 'expected': 3, 'cached': 1, 'missing': [2, 3]},
        ])
        self.assertIn('empty_verse_text', {item['kind'] for item in result['findings']})
        self.assertIn('chapter_not_in_cached_catalogue', {item['kind'] for item in result['findings']})

    def test_offline_mode_blocks_cache_misses_and_preserves_cache_on_refresh(self):
        client = CachedBibleApiClient('test')
        client.cache = SimpleCache(Path(self.directory.name) / 'client.json')
        client.cache.set_value('cached', 'content')
        with patch.dict(os.environ, {'BIBLE_API_OFFLINE': '1'}), \
                patch('requests.get', side_effect=AssertionError('Network access forbidden')) as network:
            self.assertEqual(client.get('cached'), 'content')
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                client.get('missing')
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                client.refresh('cached')
            self.assertEqual(client.cache.get_value('cached'), 'content')
            network.assert_not_called()

    def test_manage_command_blocks_network_before_django_startup(self):
        self.write_cache(dict([passage_entry('TIT.1.1-TIT.1.1', '[1] Synthetic text.')]))
        project = Path(__file__).resolve().parents[1]
        code = (
            "import runpy,sys; from unittest.mock import patch; "
            f"sys.argv=['manage.py','check_bible_numbering','--no-save','--cache-path',{str(self.path)!r}]; "
            "\nwith patch('requests.get',side_effect=AssertionError('Network forbidden')) as network:\n"
            " runpy.run_path('manage.py',run_name='__main__')\n"
            " network.assert_not_called()\n"
        )
        environment = os.environ.copy()
        environment.pop('BIBLE_API_OFFLINE', None)
        result = subprocess.run(
            [sys.executable, '-c', code], cwd=project, env=environment,
            capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('API requests: 0', result.stdout)


class NumberingReviewTest(TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'cache.json'
        self.path.write_text(json.dumps(dict([
            passage_entry('TIT.1.1-TIT.1.1', '[1] Synthetic text.'),
        ])), encoding='utf-8')

    def test_scan_creates_checklist_but_never_confirms_or_rewrites_human_review(self):
        call_command('check_bible_numbering', cache_path=self.path, stdout=io.StringIO())
        review = BibleNumberingReview.objects.get(bible_id='test')
        self.assertEqual(review.checks.count(), 5)
        self.assertEqual(set(review.checks.values_list('status', flat=True)), {'pending'})
        review.edition = 'Test edition'
        review.save(update_fields=['edition'])
        check = review.checks.get(scope='structure')
        check.status = BibleNumberingCheck.Status.CONFIRMED
        check.checked_passages = 'Titus 1:1'
        check.source = 'Printed edition'
        check.notes = 'Compared against the same edition.'
        check.mapping_revision = numbering_mapping_revision()
        check.reviewed_edition = review.edition
        check.save()
        call_command('check_bible_numbering', cache_path=self.path, stdout=io.StringIO())
        check.refresh_from_db()
        self.assertEqual(check.status, 'confirmed')
        self.assertEqual(check.source, 'Printed edition')
        self.assertFalse(check_needs_revalidation(check))
        with patch('walkasjesus_app.lib.bible_numbering_review.numbering_mapping_revision', return_value='changed'):
            self.assertTrue(check_needs_revalidation(check))
        check.review.edition = 'New edition'
        self.assertTrue(check_needs_revalidation(check))

    def test_confirming_requires_scope_source_evidence_and_issues_require_next_action(self):
        review = BibleNumberingReview.objects.create(bible_id='test', edition='Test edition')
        check = BibleNumberingCheck(review=review, scope='structure', status='confirmed')
        with self.assertRaises(ValidationError) as error:
            check.full_clean()
        self.assertEqual(set(error.exception.message_dict), {'checked_passages', 'source', 'notes'})
        review.edition = ''
        with self.assertRaises(ValidationError) as error:
            check.full_clean()
        self.assertIn('__all__', error.exception.message_dict)
        check.status = 'issue'
        with self.assertRaises(ValidationError) as error:
            check.full_clean()
        self.assertIn('follow_up', error.exception.message_dict)

    def test_no_save_and_invalid_files_do_not_create_dossiers(self):
        output = Path(self.directory.name) / 'report.json'
        call_command('check_bible_numbering', cache_path=self.path, no_save=True, output=output, stdout=io.StringIO())
        self.assertFalse(BibleNumberingReview.objects.exists())
        self.assertEqual(json.loads(output.read_text())['api_requests'], 0)
        self.path.write_text('invalid JSON', encoding='utf-8')
        with self.assertRaises(CommandError):
            call_command('check_bible_numbering', cache_path=self.path, stdout=io.StringIO())

    def test_report_cannot_overwrite_cache_and_findings_can_fail_a_cron_run(self):
        original = self.path.read_bytes()
        with self.assertRaisesRegex(CommandError, 'must not overwrite'):
            call_command('check_bible_numbering', cache_path=self.path, output=self.path, stdout=io.StringIO())
        self.assertEqual(self.path.read_bytes(), original)
        self.path.write_text(json.dumps(dict([
            passage_entry('TIT.1.1-TIT.1.1', '[2] Wrong reference.'),
        ])), encoding='utf-8')
        with self.assertRaisesRegex(CommandError, 'structural findings'):
            call_command(
                'check_bible_numbering', cache_path=self.path, no_save=True,
                fail_on_findings=True, stdout=io.StringIO(),
            )

    def test_admin_saves_evidence_and_reviewer_without_changing_mapping(self):
        user = get_user_model().objects.create_superuser(username='numbering-reviewer', password='test-password')
        review = BibleNumberingReview.objects.create(bible_id='test')
        ensure_numbering_checklist(review)
        checks = list(review.checks.order_by('pk'))
        self.client.force_login(user)
        add_url = reverse('admin:commandments_app_biblenumberingreview_add')
        self.assertEqual(self.client.get(add_url).status_code, 200)
        response = self.client.post(add_url, {
            'bible_id': 'other-test', 'edition': 'Test edition', 'notes': '', '_save': 'Save',
            'checks-TOTAL_FORMS': '0', 'checks-INITIAL_FORMS': '0',
            'checks-MIN_NUM_FORMS': '0', 'checks-MAX_NUM_FORMS': '0',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BibleNumberingReview.objects.get(bible_id='other-test').checks.count(), 5)
        url = reverse('admin:commandments_app_biblenumberingreview_change', args=[review.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = {
            'edition': 'Test edition', 'notes': '', '_save': 'Save',
            'checks-TOTAL_FORMS': '5', 'checks-INITIAL_FORMS': '5',
            'checks-MIN_NUM_FORMS': '0', 'checks-MAX_NUM_FORMS': '5',
        }
        for index, check in enumerate(checks):
            data.update({
                f'checks-{index}-id': str(check.pk), f'checks-{index}-review': str(review.pk),
                f'checks-{index}-status': 'pending', f'checks-{index}-checked_passages': '',
                f'checks-{index}-source': '', f'checks-{index}-notes': '', f'checks-{index}-follow_up': '',
            })
        data.update({
            'checks-0-status': 'confirmed', 'checks-0-checked_passages': 'Titus 1:1',
            'checks-0-source': 'Printed test edition', 'checks-0-notes': 'References and boundaries compared.',
        })
        revision = numbering_mapping_revision()
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        checks[0].refresh_from_db()
        self.assertEqual(checks[0].reviewed_by, user)
        self.assertIsNotNone(checks[0].reviewed_at)
        self.assertEqual(checks[0].mapping_revision, revision)
        self.assertEqual(checks[0].reviewed_edition, 'Test edition')
        self.client.logout()
        self.assertEqual(self.client.post(url, data).status_code, 302)
