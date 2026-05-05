from html import escape
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from walkasjesus_app.models import (
    BibleBooks,
    BibleTranslation,
    Commandment,
    LawOfMessiah,
    LawOfMessiahBibleReference,
    PrimaryBibleReference,
)


def _mocked_api_bible_verses(api_bible, _book, _start_chapter, _start_verse, _end_chapter, _end_verse):
    api_bible.copyright = f'Copyright for {api_bible.name}'
    return f'MOCK_VERSE_FOR_{api_bible.id}'


class LanguageBibleSwitchFlowTest(TestCase):
    step_id = 54
    law_id = 'GB70'

    @classmethod
    def setUpTestData(cls):
        cls.bible_translation = BibleTranslation()
        cls.en_bibles = sorted(
            [b for b in cls.bible_translation.all_enabled() if b.language == 'en'],
            key=lambda b: b.id,
        )
        cls.nl_bibles = sorted(
            [b for b in cls.bible_translation.all_enabled() if b.language == 'nl'],
            key=lambda b: b.id,
        )

        if len(cls.en_bibles) < 2:
            raise AssertionError('Expected at least 2 enabled English Bible translations for this test.')
        if len(cls.nl_bibles) < 2:
            raise AssertionError('Expected at least 2 enabled Dutch Bible translations for this test.')

        step, _ = Commandment.objects.get_or_create(
            id=cls.step_id,
            defaults={
                'title': 'Test Step 54',
                'title_negative': 'Test Step 54 Negative',
            },
        )
        if not step.primarybiblereference_set.exists():
            PrimaryBibleReference.objects.create(
                commandment=step,
                book=BibleBooks.Matthew.name,
                begin_chapter=5,
                begin_verse=14,
                end_chapter=5,
                end_verse=16,
            )

        law, _ = LawOfMessiah.objects.get_or_create(
            id=cls.law_id,
            defaults={
                'source_dataset': LawOfMessiah.SOURCE_DATASET_NT,
                'title': 'Test Law GB70',
                'commandment': 'Test law commandment',
                'commandment_type': LawOfMessiah.COMMANDMENT_TYPE_POSITIVE,
                'is_unique': True,
            },
        )
        if not law.bible_reference_rows.exists():
            LawOfMessiahBibleReference.objects.create(
                law_of_messiah=law,
                reference_type=LawOfMessiahBibleReference.TYPE_KEY_NT,
                book=BibleBooks.Matthew.name,
                begin_chapter=5,
                begin_verse=3,
                end_chapter=5,
                end_verse=5,
            )

    def setUp(self):
        cache.clear()

    def _switch_language(self, language_code, next_url, bible_id):
        response = self.client.post(
            reverse('commandments:language_switch'),
            {
                'language': language_code,
                'next': next_url,
                'bible_id': bible_id,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, language_code)
        payload = response.json()
        self.assertIn('redirect_url', payload)
        return payload['redirect_url']

    def _assert_verse_fetch_uses_bible(self, verses_url, expected_bible_id):
        response = self.client.post(verses_url)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('verses', payload)
        self.assertTrue(payload['verses'])

        combined_text = ' '.join(str(value) for value in payload['verses'].values())
        self.assertIn(f'MOCK_VERSE_FOR_{expected_bible_id}', combined_text)

    def _assert_page_has_expected_copyright(self, page_url, expected_bible):
        page_response = self.client.get(page_url)
        self.assertEqual(page_response.status_code, 200)
        html = page_response.content.decode('utf-8', errors='ignore')
        expected_copyright = f'Copyright for {expected_bible.name}'
        self.assertIn(escape(expected_copyright), html)

    @patch('bible_lib.bible_api.api_bible.ApiBible.verses', new=_mocked_api_bible_verses)
    def test_step_and_law_language_and_bible_switching(self):
        for language_code, bibles in [('en', self.en_bibles), ('nl', self.nl_bibles)]:
            first_bible = bibles[0]
            second_bible = bibles[1]

            with override(language_code):
                step_verses_url = reverse('commandments:commandment_verses', args=[self.step_id])
                law_verses_url = reverse('commandments:law_of_messiah_verses', args=[self.law_id])

            for view_name, args, verses_url in [
                ('commandments:detail', [self.step_id], step_verses_url),
                ('commandments:law_of_messiah_detail', [self.law_id], law_verses_url),
            ]:
                with self.subTest(language=language_code, view=view_name, flow='switch-language'):
                    with override(language_code):
                        localized_next = reverse(view_name, args=args)

                    redirect_url = self._switch_language(language_code, localized_next, first_bible.id)
                    with override(language_code):
                        expected_localized = reverse(view_name, args=args)
                    self.assertEqual(redirect_url, expected_localized)

                    self._assert_verse_fetch_uses_bible(verses_url, first_bible.id)
                    self._assert_page_has_expected_copyright(redirect_url, first_bible)

                with self.subTest(language=language_code, view=view_name, flow='switch-only-bible'):
                    redirect_after_bible_only = self._switch_language(language_code, redirect_url, second_bible.id)
                    self.assertEqual(redirect_after_bible_only, redirect_url)

                    self._assert_verse_fetch_uses_bible(verses_url, second_bible.id)
                    self._assert_page_has_expected_copyright(redirect_url, second_bible)
