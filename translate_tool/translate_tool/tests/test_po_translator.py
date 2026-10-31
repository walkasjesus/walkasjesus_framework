import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import polib
import requests

from translate_tool import PoTranslator
from translate_tool.local_translator import LocalPoTranslator


class PoTranslatorTest(TestCase):
    def setUp(self):
        self.translator = PoTranslator()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'django.po'

    def save_catalog(self, entries):
        po = polib.POFile()
        po.metadata = {'Plural-Forms': 'nplurals=3; plural=(n == 1 ? 0 : n == 2 ? 1 : 2);'}
        po.extend(entries)
        po.save(self.path)

    def test_existing_translations_are_preserved(self):
        self.save_catalog([
            polib.POEntry(msgid='Hello', msgstr='Existing'),
            polib.POEntry(msgid='Welcome'),
            polib.POEntry(msgid='Old', obsolete=True),
        ])
        with patch.object(self.translator, '_translate_text', return_value='Translated') as translate:
            self.translator.translate(self.path, 'en', 'he')
        translate.assert_called_once_with('Welcome', 'en', 'he')
        self.assertEqual(polib.pofile(self.path).find('Hello').msgstr, 'Existing')

    def test_scope_and_limit_preserve_unselected_entries(self):
        self.save_catalog([
            polib.POEntry(msgid='Story'),
            polib.POEntry(msgid='Menu', occurrences=[('templates/base.html', '1')]),
            polib.POEntry(msgid='Settings', occurrences=[('templates/base.html', '2')]),
        ])
        with patch.object(self.translator, '_translate_text', return_value='Translated') as translate:
            completed = self.translator.translate(
                self.path, 'en', 'he', entry_filter=lambda entry: bool(entry.occurrences), limit=1,
            )
        self.assertEqual(completed, 1)
        translate.assert_called_once_with('Menu', 'en', 'he')
        po = polib.pofile(self.path)
        self.assertEqual(po.find('Story').msgstr, '')
        self.assertEqual(po.find('Settings').msgstr, '')

    def test_requests_are_paced_across_chunks(self):
        self.translator = PoTranslator(request_interval=2)
        with patch('translate_tool.po_translator.requests.get') as get:
            get.return_value.json.return_value = [[['Translated']]]
            with patch('translate_tool.po_translator.time.monotonic', side_effect=[10, 10.5, 12]):
                with patch('translate_tool.po_translator.time.sleep') as sleep:
                    self.translator._translate_chunk('First', 'en', 'he')
                    self.translator._translate_chunk('Second', 'en', 'he')
        sleep.assert_called_once_with(1.5)

    def test_progress_is_saved_and_service_errors_propagate(self):
        self.save_catalog([polib.POEntry(msgid='First'), polib.POEntry(msgid='Second')])
        with patch.object(self.translator, '_translate_text', side_effect=['Translated', requests.HTTPError('429')]):
            with self.assertRaises(requests.HTTPError):
                self.translator.translate(self.path, 'en', 'he')
        po = polib.pofile(self.path)
        self.assertEqual(po.find('First').msgstr, 'Translated')
        self.assertEqual(po.find('Second').msgstr, '')

    def test_tokens_and_boundary_newlines_are_preserved(self):
        text = '\n<b>Hello %(name)s</b>\n'
        with patch.object(self.translator, '_translate_chunk', side_effect=lambda text, *_: text):
            self.assertEqual(self.translator._translate_text(text, 'en', 'he'), text)

    def test_damaged_tokens_are_rejected(self):
        with patch.object(self.translator, '_translate_chunk', return_value='Missing token'):
            with self.assertRaisesRegex(ValueError, 'protected placeholders'):
                self.translator._translate_text('Hello %(name)s', 'en', 'he')

    def test_empty_service_response_is_rejected(self):
        with patch('translate_tool.po_translator.requests.get') as get:
            get.return_value.json.return_value = []
            with self.assertRaisesRegex(ValueError, 'no translated text'):
                self.translator._translate_chunk('Hello', 'en', 'he')

    def test_hebrew_plural_forms_and_fuzzy_entries(self):
        self.save_catalog([
            polib.POEntry(msgid='One item', msgid_plural='Many items'),
            polib.POEntry(msgid='Hello', msgstr='Old', flags=['fuzzy']),
        ])
        with patch.object(self.translator, '_translate_text', side_effect=['Singular', 'Plural', 'New']):
            self.translator.translate(self.path, 'en', 'he')
        po = polib.pofile(self.path)
        self.assertEqual(po.find('One item').msgstr_plural, {0: 'Singular', 1: 'Plural', 2: 'Plural'})
        self.assertEqual(po.find('Hello').msgstr, 'New')
        self.assertNotIn('fuzzy', po.find('Hello').flags)

    def test_local_drafts_are_reviewable_resumable_and_not_published(self):
        translator = LocalPoTranslator('/unused')
        self.save_catalog([polib.POEntry(msgid='Welcome')])
        with patch.object(translator, '_translate_text', return_value='Draft'):
            self.assertEqual(translator.translate(self.path, 'en', 'he'), 1)
        po = polib.pofile(self.path)
        entry = po.find('Welcome')
        self.assertIn('fuzzy', entry.flags)
        self.assertIn('review in Rosetta', entry.tcomment)
        self.assertFalse(entry.translated())
        with patch.object(translator, '_translate_text') as inference:
            self.assertEqual(translator.translate(self.path, 'en', 'he'), 0)
        inference.assert_not_called()
        import gettext
        import io
        self.assertEqual(gettext.GNUTranslations(io.BytesIO(po.to_binary())).gettext('Welcome'), 'Welcome')
        entry.flags.remove('fuzzy')
        self.assertEqual(gettext.GNUTranslations(io.BytesIO(po.to_binary())).gettext('Welcome'), 'Draft')

    def test_local_model_never_receives_placeholders_or_markup(self):
        translator = LocalPoTranslator('/unused')
        text = '\n<b>Hello %(name)s</b>\n{{ value }} {% tag %}'
        with patch.object(translator, '_translate_chunk', side_effect=lambda value, *_: value) as inference:
            self.assertEqual(translator._translate_text(text, 'en', 'he'), text)
        self.assertEqual([call.args[0] for call in inference.call_args_list], ['Hello'])

    def test_missing_local_model_fails_explicitly(self):
        translator = LocalPoTranslator('/missing/waj-model')
        with self.assertRaisesRegex(ValueError, 'metadata not found'):
            translator._translate_chunk('Hello', 'en', 'he')
