import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bible_lib import BibleBooks as BibleLibBibleBooks
from bible_lib.bible_api.api_bible import ApiBible
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _load_chapter_index,
    _primary_chapter_index_bible_id,
    _study_verse_references,
    _study_reference_metadata,
    _study_verse_text,
)
from walkasjesus_app.lib.strongs_service import (
    _stepbible_rows_for_verse,
    english_alignment_payload,
    english_hebrew_references,
    hebrew_english_references,
    hebrew_reference_metadata,
    psalm_english_reference,
    psalm_hebrew_reference,
    psalm_verse_mapping,
)
from walkasjesus_app.models.bibles import LocalStatenvertalingBible
from walkasjesus_app.views.admin.admin_bible_view import AdminBibleView


class BibleNumberingAdminTest(TestCase):
    @patch('walkasjesus_app.views.admin.admin_bible_view.CacheController')
    @patch('walkasjesus_app.views.admin.admin_bible_view.Services')
    @patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslationMetaData')
    @patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslation')
    @patch.object(AdminBibleView, 'bible_count_in_cache', return_value=(1, 2))
    def test_numbering_profiles_and_limitations_are_visible_only_to_staff(self, count, translations, metadata, services, controller):
        bibles = [
            SimpleNamespace(id='unknown', name='Unknown translation', abbreviation='UNK', language='en'),
            SimpleNamespace(id='hsv', name='Herziene Statenvertaling', abbreviation='HSV', language='nl'),
        ]
        translations.return_value.all.return_value = bibles
        metadata.objects.filter.return_value.exists.return_value = True
        metadata.objects.get.return_value.is_enabled = True
        services.return_value.cache.cache_items_not_persisted = 0
        request = RequestFactory().get('/admin/bibles/')
        request.session = {}
        request.user = SimpleNamespace(is_active=True, is_staff=True)
        response = AdminBibleView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verse numbering profile and limitations')
        self.assertContains(response, 'Verse numbering for this translation has not been verified.')
        self.assertContains(response, 'not independently verified')
        request.user.is_staff = False
        self.assertEqual(AdminBibleView.as_view()(request).status_code, 302)


class PsalmVersificationTest(SimpleTestCase):
    def test_hebrew_heading_and_body_have_distinct_original_rows(self):
        title = _stepbible_rows_for_verse('Psalms', 30, 1, 'hebrew')
        body = _stepbible_rows_for_verse('Psalms', 30, 2, 'hebrew')
        self.assertEqual(len(title), 5)
        self.assertTrue(all(row.startswith('Psa.30.0(30.1)#') for row in title))
        self.assertTrue(all(row.startswith('Psa.30.1(30.2)#') for row in body))
        self.assertEqual(body, _stepbible_rows_for_verse('Psalms', 30, 1))

    def test_mapping_comes_from_stepbible_and_includes_last_verse(self):
        self.assertEqual(psalm_english_reference(30, 1), (30, 0))
        self.assertEqual(psalm_english_reference(30, 2), (30, 1))
        self.assertEqual(psalm_english_reference(30, 13), (30, 12))
        self.assertEqual(psalm_hebrew_reference(30, 12), (30, 13))
        self.assertEqual(max(v for c, v in psalm_verse_mapping() if c == 30), 13)
        self.assertEqual(psalm_english_reference(1, 1), (1, 1))

    def test_kjv_heading_does_not_fetch_the_first_body_verse(self):
        bible = Mock(name='kjv')
        bible.name = 'King James Version'
        bible.abbreviation = 'KJV'
        bible.language = 'en'
        bible.verses.return_value = 'Body verse.'
        self.assertEqual(_study_verse_text(bible, 'Psalms', 30, 1, 'hebrew'), '')
        bible.verses.assert_not_called()
        _study_verse_text(bible, 'Psalms', 30, 2, 'hebrew')
        bible.verses.assert_called_once_with(BibleLibBibleBooks.Psalms, 30, 1, 30, 1)

    def test_native_hebrew_translations_are_not_shifted(self):
        bible = Mock()
        bible.name = 'Herziene Statenvertaling'
        bible.abbreviation = 'HSV'
        bible.language = 'nl'
        bible.verses.return_value = 'Body verse.'
        _study_verse_text(bible, 'Psalms', 30, 2, 'hebrew')
        bible.verses.assert_called_once_with(BibleLibBibleBooks.Psalms, 30, 2, 30, 2)

    def test_statenvertaling_embedded_numbers_split_heading_and_body(self):
        bible = LocalStatenvertalingBible('svv-statenvertaling')
        self.assertEqual(bible.psalm_study_verse(30, 1), 'Een psalm, een lied der inwijding van Davids huis.')
        self.assertTrue(bible.psalm_study_verse(30, 2).startswith('Ik zal U verhogen'))
        self.assertTrue(bible.psalm_study_verse(30, 3).startswith('Heere, mijn God!'))
        for verse in range(1, 14):
            text = bible.psalm_study_verse(30, verse)
            self.assertTrue(text)
            self.assertNotIn('[030:', text)


class HebrewVersificationTest(SimpleTestCase):
    def test_hebrew_rows_and_cross_chapter_mappings_come_from_stepbible(self):
        rows = _stepbible_rows_for_verse('Hosea', 2, 3, 'hebrew')
        self.assertTrue(rows)
        self.assertTrue(all(row.startswith('Hos.2.1(2.3)#') for row in rows))
        self.assertEqual(hebrew_english_references('Hosea', 2, 3), ((2, 1),))
        self.assertEqual(english_hebrew_references('Hosea', 2, 1), ((2, 3),))
        self.assertEqual(hebrew_english_references('Joel', 3, 1), ((2, 28),))
        self.assertEqual(hebrew_english_references('ChroniclesFirstBook', 5, 27), ((6, 1),))
        self.assertEqual(hebrew_reference_metadata()['chapters']['Joel'], 4)
        self.assertEqual(hebrew_reference_metadata()['chapters']['Malachi'], 3)
        self.assertEqual(_study_reference_metadata()['dutch_to_hebrew']['Hosea']['1:12'], [(2, 3)])
        self.assertEqual(_study_reference_metadata()['dutch_to_hebrew']['Joel']['2:28'], [(3, 1)])

    def test_hosea_translations_use_their_own_numbers(self):
        sv = LocalStatenvertalingBible('svv-statenvertaling')
        hsv = Mock(name='HSV')
        hsv.name = 'Herziene Statenvertaling'
        hsv.abbreviation = 'HSV'
        hsv.language = 'nl'
        kjv = Mock(name='KJV')
        kjv.name = 'King James Version'
        kjv.abbreviation = 'KJV'
        kjv.language = 'en'
        naardense = Mock(name='Naardense')
        naardense.name = 'Naardense Bijbel 2024'
        naardense.language = 'nl'
        self.assertEqual(_study_verse_references(sv, 'Hosea', 2, 3, 'hebrew')[:2], (((2, 1),), ((1, 12),)))
        self.assertEqual(_study_verse_references(hsv, 'Hosea', 2, 3, 'hebrew')[:2], (((1, 12),), ((1, 12),)))
        self.assertEqual(_study_verse_references(kjv, 'Hosea', 2, 3, 'hebrew')[:2], (((2, 1),), ((2, 1),)))
        self.assertEqual(_study_verse_references(naardense, 'Hosea', 2, 3, 'hebrew')[:2], (((2, 3),), ((2, 3),)))
        self.assertTrue(_study_verse_text(sv, 'Hosea', 2, 3, 'hebrew').startswith('Zegt tot uw broederen'))

    def test_unverified_and_partial_verse_boundaries_are_not_silent(self):
        unknown = Mock()
        unknown.name = 'Unknown translation'
        unknown.abbreviation = 'UNKNOWN'
        unknown.language = 'nl'
        sources, labels, warning = _study_verse_references(unknown, 'Hosea', 2, 3, 'hebrew')
        self.assertEqual((sources, labels), ((), ()))
        self.assertIn('not verified', warning)
        sources, labels, warning = _study_verse_references(unknown, 'Genesis', 1, 1, 'hebrew')
        self.assertEqual((sources, labels), (((1, 1),), ((1, 1),)))
        self.assertIn('not been verified', warning)
        kjv = Mock()
        kjv.name = 'King James Version'
        kjv.abbreviation = 'KJV'
        kjv.language = 'en'
        sources, _, warning = _study_verse_references(kjv, 'Numbers', 25, 19, 'hebrew')
        self.assertEqual(sources, ((26, 1),))
        self.assertIn('boundaries differ', warning)

    @patch('walkasjesus_app.lib.strongs_service._align_english_words')
    def test_partial_verse_alignment_does_not_guess_word_links(self, align):
        cache.clear()
        payload = english_alignment_payload(
            'Numbers', 25, 19, 'These are the words', tagged_source='kjv',
            reference_system='hebrew',
        )
        self.assertEqual(payload['aligned_count'], 0)
        self.assertEqual(payload['tokens'], [])
        align.assert_not_called()


class ChapterIndexCoverageTest(SimpleTestCase):
    def test_primary_index_covers_all_chapters(self):
        primary = _load_chapter_index()[_primary_chapter_index_bible_id()]
        for book, count in _CANONICAL_CHAPTER_COUNTS.items():
            with self.subTest(book=book):
                self.assertEqual(set(primary[book]), {str(chapter) for chapter in range(1, count + 1)})
                self.assertTrue(all(1 <= maximum <= 176 for maximum in primary[book].values()))
        self.assertEqual(primary['Psalms']['77'], 20)
        self.assertEqual(primary['Psalms']['119'], 176)
        self.assertEqual(primary['John']['10'], 42)

    def test_local_rebuild_preserves_other_translations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'index.json'
            path.write_text(json.dumps({'other': {'Titus': {'1': 16}}}), encoding='utf-8')
            with override_settings(
                BIBLE_STUDY_CHAPTER_INDEX_PATH=str(path),
                BIBLE_STUDY_CHAPTER_INDEX_PRIMARY_BIBLE_ID='de4e12af7f28f599-01',
            ):
                call_command('build_bible_study_chapter_index', local_kjv=True)
            index = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(index['other'], {'Titus': {'1': 16}})
            self.assertEqual(sum(len(chapters) for chapters in index['de4e12af7f28f599-01'].values()), 1189)

    def test_local_rebuild_rejects_missing_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            with override_settings(BASE_DIR=directory, BIBLE_STUDY_CHAPTER_INDEX_PRIMARY_BIBLE_ID='de4e12af7f28f599-01'):
                with self.assertRaisesRegex(CommandError, 'Missing tagged KJV data'):
                    call_command('build_bible_study_chapter_index', local_kjv=True)


@override_settings(DISABLED_BIBLE_TRANSLATIONS=[], DISABLE_CACHE_FOR_DEBUG=True)
class BibleStudyPassagesTest(TestCase):
    def setUp(self):
        cache.clear()
        self.bible = ApiBible(api_key='test', bible_id='bgt')
        self.bible.name = 'BGT'
        self.bible.language = 'nl'

    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_psalm_77_and_other_multi_digit_chapters_have_metadata(self, translations):
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        for book, chapter, maximum in [('Psalms', 77, 20), ('Psalms', 119, 176), ('John', 10, 42)]:
            with self.subTest(book=book, chapter=chapter):
                response = self.client.get(reverse('commandments:bible_study_chapter_meta'), {
                    'book': book, 'chapter': chapter, 'bible_id': self.bible.id,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['max_verse'], maximum)

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_titus_bgt_combined_verses_are_not_empty(self, translations, _quota):
        translations.return_value.get.return_value = self.bible
        self.bible.client.get = Mock(side_effect=[
            json.dumps({'data': {'content': '[1-4] Combined passage.', 'copyright': 'test'}})
            for _ in range(4)
        ] + [json.dumps({'data': {'content': '[5] Next verse.', 'copyright': 'test'}})])
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 5,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses'], {
            '1': 'Combined passage.', '2': 'Combined passage.', '3': 'Combined passage.',
            '4': 'Combined passage.', '5': 'Next verse.',
        })

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_unverified_numbering_is_hidden_but_unavailable_passages_remain_explicit(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        with patch.object(self.bible, 'verses', return_value='Verse text.') as verses:
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'bgt', 'book': 'Exodus', 'chapter': 18,
                'start_verse': 11, 'end_verse': 15, 'reference_system': 'hebrew',
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['verse_warnings'], {})
            self.assertEqual(response.json()['verses']['11'], 'Verse text.')
            verses.reset_mock()
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'bgt', 'book': 'Hosea', 'chapter': 2,
                'start_verse': 3, 'end_verse': 3, 'reference_system': 'hebrew',
            })
        self.assertEqual(response.json()['verses'], {'3': ''})
        self.assertIn('Choose another translation', response.json()['verse_warnings']['3'])
        self.assertNotIn('not verified', response.json()['verse_warnings']['3'])
        verses.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_hebrew_psalm_comparison_exposes_kjv_source_numbers(self, translations, quota):
        self.bible.name = 'King James Version'
        self.bible.language = 'en'
        translations.return_value.get.return_value = self.bible
        with patch.object(self.bible, 'verses', return_value='Body verse.') as verses:
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'bgt', 'book': 'Psalms', 'chapter': 30,
                'start_verse': 1, 'end_verse': 2, 'reference_system': 'hebrew',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses'], {'1': '', '2': 'Body verse.'})
        self.assertEqual(response.json()['verse_references'], {'1': '—', '2': '30:1'})
        verses.assert_called_once_with(BibleLibBibleBooks.Psalms, 30, 1, 30, 1)
        quota.assert_called_once()

    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_hebrew_psalm_chapter_meta_is_independent_of_translation(self, translations):
        translations.return_value.get.return_value = self.bible
        response = self.client.get(reverse('commandments:bible_study_chapter_meta'), {
            'bible_id': 'bgt', 'book': 'Psalms', 'chapter': 30, 'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['max_verse'], 13)

    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_hebrew_joel_chapter_meta_uses_hebrew_not_translation_numbering(self, translations):
        translations.return_value.get.return_value = self.bible
        response = self.client.get(reverse('commandments:bible_study_chapter_meta'), {
            'bible_id': 'bgt', 'book': 'Joel', 'chapter': 3, 'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['max_verse'], 5)

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_hosea_hebrew_comparison_fetches_hsv_source_reference(self, translations, _quota):
        self.bible.name = 'Herziene Statenvertaling'
        self.bible.abbreviation = 'HSV'
        translations.return_value.get.return_value = self.bible
        with patch.object(self.bible, 'verses', return_value='Zeg tegen uw broeders.') as verses:
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'bgt', 'book': 'Hosea', 'chapter': 2,
                'start_verse': 3, 'end_verse': 3, 'reference_system': 'hebrew',
            })
        self.assertEqual(response.json()['verses'], {'3': 'Zeg tegen uw broeders.'})
        self.assertEqual(response.json()['verse_references'], {'3': '1:12'})
        verses.assert_called_once_with(BibleLibBibleBooks.Hosea, 1, 12, 1, 12)

    @patch('walkasjesus_app.views.bible_study_view.localized_original_text_payload')
    def test_original_endpoint_passes_hebrew_numbering(self, original):
        original.return_value = {'sentence': 'Title'}
        response = self.client.post(reverse('commandments:bible_study_original_text'), {
            'book': 'Psalms', 'chapter': 30, 'start_verse': 1,
            'end_verse': 1, 'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(original.call_args.kwargs['reference_system'], 'hebrew')

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_english_detail_link_is_converted_before_rendering(self, translations, _quota):
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        with patch.object(self.bible, 'verses', return_value='Verse text.'):
            response = self.client.get(reverse('commandments:bible_study'), {
                'bible_id': 'bgt', 'book': 'Psalms', 'chapter': 30,
                'start_verse': 1, 'end_verse': 5, 'reference_system': 'english',
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_start_verse'], 2)
        self.assertEqual(response.context['selected_end_verse'], 6)
        self.assertNotContains(response, '<small class="bs-source-reference d-block text-muted">Psalms')

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_only_differing_source_reference_is_shown_on_page(self, translations, _quota):
        self.bible.name = 'King James Version'
        self.bible.language = 'en'
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        with patch.object(self.bible, 'verses', return_value='Verse text.'):
            response = self.client.get(reverse('commandments:bible_study'), {
                'bible_id': 'bgt', 'book': 'Psalms', 'chapter': 30,
                'start_verse': 2, 'end_verse': 2,
            })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="bs-source-reference d-block text-muted">Psalms 30:1</small>')

    @patch('walkasjesus_app.views.bible_study_view.english_alignment_payload')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_word_links_use_the_same_hebrew_reference_system(self, translations, alignment):
        self.bible.language = 'en'
        translations.return_value.get.return_value = self.bible
        alignment.return_value = {'tokens': [], 'aligned_count': 0}
        response = self.client.post(reverse('commandments:bible_study_word_alignment'), {
            'bible_id': 'bgt', 'book': 'Psalms', 'chapter': 30,
            'verses': json.dumps({'2': 'Body verse.'}), 'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(alignment.call_args.kwargs['reference_system'], 'hebrew')
