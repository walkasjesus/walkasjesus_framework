from django.core.cache import cache
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from walkasjesus_app.models import (
    BibleBooks,
    Commandment,
    LawOfMessiah,
    LawOfMessiahBibleReference,
    Lesson,
)


class DutchTranslationPagesTest(TestCase):
    law_id = 'GB70'
    step_id = 54
    lesson_id = 901

    @classmethod
    def setUpTestData(cls):
        commandment, _ = Commandment.objects.get_or_create(
            id=cls.step_id,
            defaults={
                'title': 'Test Step 54',
                'title_negative': 'Test Step 54 Negative',
            },
        )

        Lesson.objects.get_or_create(
            id=cls.lesson_id,
            defaults={
                'title': 'Test Lesson 901',
                'commandment': commandment,
            },
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

    def test_nl_pages_do_not_show_known_english_law_strings(self):
        with override('nl'):
            next_url = reverse('commandments:index')
        switch_response = self.client.post(
            reverse('commandments:language_switch'),
            {'language': 'nl', 'next': next_url},
        )
        self.assertEqual(switch_response.status_code, 200)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'nl')

        page_expectations = [
            {
                'url_name': 'commandments:law_of_messiah_listing',
                'args': [],
                'must_not_contain': [
                    'Volume 1 & 2',
                    'Volume 3',
                ],
                'must_contain': [
                    'Deel 1 & 2',
                    'Deel 3',
                ],
            },
            {
                'url_name': 'commandments:law_of_messiah_detail',
                'args': [self.law_id],
                'must_not_contain': [
                    'Source and License',
                    'Based on <em>The Law of Messiah - Torah from a New Covenant Perspective</em> by Michael Rudolph and Daniel C. Juster.',
                    'License: CC BY-ND 4.0 (Attribution required, NoDerivatives).',
                    'NCLA deviation:',
                    'Volume 1 & 2',
                    'Volume 3',
                ],
                'must_contain': [
                    'Bron en licentie',
                    'Bronmateriaal: <em>The Law of Messiah - Torah from a New Covenant Perspective</em> door Michael Rudolph en Daniel C. Juster.',
                    'Licentie: CC BY-ND 4.0 (naamsvermelding vereist, geen afgeleide producten).',
                    'NCLA-afwijking:',
                    'Deel 1 & 2',
                    'Deel 3',
                ],
            },
        ]

        for case in page_expectations:
            with self.subTest(url_name=case['url_name']):
                with override('nl'):
                    page_url = reverse(case['url_name'], args=case['args'])
                response = self.client.get(page_url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode('utf-8', errors='ignore')

                for forbidden in case['must_not_contain']:
                    self.assertNotIn(forbidden, html)

                for expected in case['must_contain']:
                    self.assertIn(expected, html)

    def test_nl_sample_across_page_types(self):
        with override('nl'):
            next_url = reverse('commandments:index')
        switch_response = self.client.post(
            reverse('commandments:language_switch'),
            {'language': 'nl', 'next': next_url},
        )
        self.assertEqual(switch_response.status_code, 200)
        self.assertEqual(self.client.cookies[settings.LANGUAGE_COOKIE_NAME].value, 'nl')

        sampled_pages = [
            {'url_name': 'commandments:index', 'args': [], 'expected': 'Wijzig taal / Bijbel'},
            {'url_name': 'commandments:listing', 'args': [], 'expected': '77 Stappen'},
            {'url_name': 'commandments:detail', 'args': [self.step_id], 'expected': 'Bijbelteksten'},
            {'url_name': 'commandments:lesson_listing', 'args': [], 'expected': 'Kinderbijbel lessen'},
            {'url_name': 'commandments:lessondetail', 'args': [self.lesson_id], 'expected': 'Les'},
            {'url_name': 'commandments:law_of_messiah_listing', 'args': [], 'expected': 'Wet van Christus'},
            {'url_name': 'commandments:law_of_messiah_detail', 'args': [self.law_id], 'expected': 'Bron en licentie'},
            {'url_name': 'commandments:vision', 'args': [], 'expected': 'Visie'},
            {'url_name': 'commandments:legalism', 'args': [], 'expected': 'Wetticisme?!'},
            {'url_name': 'commandments:privacy', 'args': [], 'expected': 'Privacybeleid'},
            {'url_name': 'commandments:termsandconditions', 'args': [], 'expected': 'Voorwaarden'},
            {'url_name': 'commandments:maimonides_listing', 'args': [], 'expected': 'Maimonides'},
        ]

        for case in sampled_pages:
            with self.subTest(url_name=case['url_name']):
                with override('nl'):
                    page_url = reverse(case['url_name'], args=case['args'])
                response = self.client.get(page_url)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode('utf-8', errors='ignore')

                self.assertIn('Wijzig taal / Bijbel', html)
                self.assertNotIn('Change language / Bible', html)
                self.assertIn(case['expected'], html)
