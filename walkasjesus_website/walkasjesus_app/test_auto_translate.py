import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from walkasjesus_app.management.commands.auto_translate import Command


class AutoTranslateCommandTest(SimpleTestCase):
    def test_locale_limits_translation_to_requested_catalog(self):
        with patch.object(Command, '_po_file_paths', return_value=iter(['/tmp/he/django.po'])) as paths:
            with patch('walkasjesus_app.management.commands.auto_translate.PoTranslator') as translator:
                call_command('auto_translate', locale=['he'])
        paths.assert_called_once_with('he')
        translator.return_value.translate.assert_called_once_with('/tmp/he/django.po', 'en', 'he')

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
