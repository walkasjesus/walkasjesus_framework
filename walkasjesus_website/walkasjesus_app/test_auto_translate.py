import tempfile
import gettext
import hashlib
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import polib
import requests
from translate_tool import PoTranslator
from django.core.management import call_command, CommandError
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from walkasjesus_app.management.commands.auto_translate import Command, is_content_entry
from walkasjesus_app.management.commands.sync_model_translations import Command as SyncCommand


class AutoTranslateCommandTest(SimpleTestCase):
    def test_locale_limits_translation_to_requested_catalog(self):
        po = polib.POFile()
        po.append(polib.POEntry(msgid='Welcome'))
        with patch.object(Command, '_po_file_paths', return_value=iter(['/tmp/he/django.po'])) as paths:
            with patch('walkasjesus_app.management.commands.auto_translate.polib.pofile', return_value=po):
                with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as translator:
                    call_command('auto_translate', locale=['he'])
        paths.assert_called_once_with('he')
        translator.return_value.translate.assert_called_once_with(
            '/tmp/he/django.po', 'en', 'he', entry_filter=None, limit=None,
        )

    def test_scope_classifies_legacy_model_and_shared_messages(self):
        self.assertTrue(is_content_entry(polib.POEntry(msgid='Step title')))
        self.assertTrue(is_content_entry(polib.POEntry(msgid='Story', occurrences=[('model:Lesson.story', '')])))
        self.assertFalse(is_content_entry(polib.POEntry(
            msgid='Shared', occurrences=[('model:Lesson.title', ''), ('templates/base.html', '1')],
        )))

    def test_dry_run_counts_ui_and_content_without_requests_or_saving(self):
        po = polib.POFile()
        po.extend([
            polib.POEntry(msgid='Menu', occurrences=[('templates/base.html', '1')]),
            polib.POEntry(msgid='Story'),
            polib.POEntry(msgid='Done', msgstr='Translated'),
            polib.POEntry(msgid='Old', obsolete=True),
        ])
        out = StringIO()
        with patch.object(Command, '_po_file_paths', return_value=['he.po']):
            with patch('walkasjesus_app.management.commands.auto_translate.polib.pofile', return_value=po):
                with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as translator:
                    translator.needs_translation.side_effect = PoTranslator.needs_translation
                    call_command('auto_translate', locale=['he'], scope='ui', dry_run=True, stdout=out)
        translator.return_value.translate.assert_not_called()
        self.assertIn('pending UI=1, content=1; scope=ui, batch=1', out.getvalue())

    def test_limit_is_shared_across_catalogs(self):
        po = polib.POFile()
        po.append(polib.POEntry(msgid='Menu', occurrences=[('templates/base.html', '1')]))
        with patch.object(Command, '_po_file_paths', return_value=['first.po', 'second.po']):
            with patch('walkasjesus_app.management.commands.auto_translate.polib.pofile', return_value=po):
                with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as translator:
                    translator.return_value.translate.return_value = 1
                    call_command('auto_translate', locale=['he'], limit=1)
        translator.return_value.translate.assert_called_once()

    def test_rate_limit_is_reported_with_retry_after(self):
        po = polib.POFile()
        po.append(polib.POEntry(msgid='Menu'))
        response = requests.Response()
        response.status_code = 429
        response.headers['Retry-After'] = '120'
        with patch.object(Command, '_po_file_paths', return_value=['he.po']):
            with patch('walkasjesus_app.management.commands.auto_translate.polib.pofile', return_value=po):
                with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as translator:
                    translator.return_value.translate.side_effect = requests.HTTPError('429', response=response)
                    with self.assertRaisesRegex(CommandError, 'Retry-After: 120'):
                        call_command('auto_translate', locale=['he'])

    def test_invalid_batch_options_are_rejected(self):
        for options in [{'limit': 0}, {'request_interval': -1}, {'request_interval': float('nan')}]:
            with self.subTest(options=options), self.assertRaises(CommandError):
                call_command('auto_translate', locale=['he'], **options)

    def test_local_provider_requires_model_path(self):
        with self.assertRaisesRegex(CommandError, '--model-path is required'):
            call_command('auto_translate', locale=['he'], provider='local')

    def test_local_provider_does_not_construct_google_translator(self):
        po = polib.POFile()
        po.append(polib.POEntry(msgid='Menu', occurrences=[('templates/base.html', '1')]))
        with patch.object(Command, '_po_file_paths', return_value=['he.po']):
            with patch('walkasjesus_app.management.commands.auto_translate.polib.pofile', return_value=po):
                with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as google:
                    google.needs_translation.return_value = True
                    with patch('walkasjesus_app.management.commands.auto_translate.LocalPoTranslator') as local:
                        call_command('auto_translate', locale=['he'], provider='local', model_path='/local/model')
        google.assert_not_called()
        local.assert_called_once_with('/local/model')
        local.return_value.translate.assert_called_once()

    def test_unknown_locale_is_rejected(self):
        with self.assertRaisesRegex(CommandError, 'Unsupported locales'):
            call_command('auto_translate', locale=['unsupported'])

    def test_missing_catalog_is_reported(self):
        with patch.object(Command, '_po_file_paths', return_value=iter([])):
            with self.assertRaisesRegex(CommandError, 'No PO files'):
                call_command('auto_translate', locale=['he'])

    def test_duplicate_and_external_catalogs_are_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = root / 'locale' / 'he' / 'LC_MESSAGES' / 'django.po'
            catalog.parent.mkdir(parents=True)
            catalog.touch()
            with patch('walkasjesus_app.management.commands.auto_translate.BASE_DIR', directory):
                with patch('walkasjesus_app.management.commands.auto_translate.LOCALE_PATHS', [
                    str(root / 'locale'), str(root / 'locale'), '/outside/locale',
                ]):
                    with patch('walkasjesus_app.management.commands.auto_translate.apps.get_app_configs', return_value=[]):
                        self.assertEqual(list(Command()._po_file_paths('he')), [str(catalog)])


class SyncTranslationSourcesTest(SimpleTestCase):
    def test_model_sources_preserve_translations_and_shared_ui_references(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'translations/locale/he/LC_MESSAGES/django.po'
            path.parent.mkdir(parents=True)
            po = polib.POFile()
            po.extend([
                polib.POEntry(msgid='Story', msgstr='Existing', obsolete=True),
                polib.POEntry(msgid='Shared', occurrences=[('templates/base.html', '1')]),
            ])
            po.save(path)
            model = Mock()
            model.objects.exclude.return_value.values_list.return_value.distinct.return_value.iterator.side_effect = (
                lambda: iter(['Story', 'Shared', 'New'])
            )
            model._meta.fields = []
            with self.settings(BASE_DIR=directory):
                with patch('walkasjesus_app.management.commands.sync_model_translations.TRANSLATABLE_MODEL_FIELDS',
                           {'Lesson': ['story']}):
                    with patch('walkasjesus_app.management.commands.sync_model_translations.apps.get_model',
                               return_value=model):
                        for _ in range(2):
                            call_command(SyncCommand(), locales=['he'])
            result = polib.pofile(path)
            self.assertEqual(result.find('Story').msgstr, 'Existing')
            self.assertFalse(result.find('Story').obsolete)
            self.assertTrue(is_content_entry(result.find('Story')))
            self.assertFalse(is_content_entry(result.find('Shared')))
            self.assertEqual(result.find('New').occurrences, [('model:Lesson.story', '')])
            self.assertEqual(len(result), 3)


class RosettaLocalDraftReviewTest(TestCase):
    def test_fuzzy_draft_can_be_reviewed_and_published_in_rosetta(self):
        user = get_user_model().objects.create_user(
            username='local-reviewer', is_staff=True, is_superuser=True,
        )
        self.client.force_login(user)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'django.po'
            po = polib.POFile()
            po.metadata = {'Language': 'he', 'Content-Type': 'text/plain; charset=UTF-8'}
            entry = polib.POEntry(
                msgid='Welcome', msgstr='Draft', flags=['fuzzy'],
                tcomment='Machine translation draft: local Argos; review in Rosetta.',
            )
            po.append(entry)
            po.save(path)
            url = reverse('rosetta-form', kwargs={'po_filter': 'project', 'lang_id': 'he', 'idx': 0})
            with patch('rosetta.views.find_pos', return_value=[str(path)]):
                response = self.client.get(url, {'msg_filter': 'fuzzy'})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Fuzzy only')
                self.assertContains(response, 'Draft')
                digest = hashlib.md5(b'WelcomeDraft').hexdigest()
                response = self.client.post(url, {f'm_{digest}': 'Approved'})
                self.assertEqual(response.status_code, 302)
            saved = polib.pofile(path)
            self.assertNotIn('fuzzy', saved.find('Welcome').flags)
            with path.with_suffix('.mo').open('rb') as compiled:
                self.assertEqual(gettext.GNUTranslations(compiled).gettext('Welcome'), 'Approved')
