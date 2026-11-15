import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from bible_lib import BibleBooks as BibleLibBibleBooks
from bible_lib.bible_api.api_bible import ApiBible
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _load_chapter_index,
    _primary_chapter_index_bible_id,
    _study_verse_text,
)
from walkasjesus_app.lib.strongs_service import (
    _stepbible_rows_for_verse,
    psalm_english_reference,
    psalm_hebrew_reference,
    psalm_verse_mapping,
)
from walkasjesus_app.models.bibles import LocalStatenvertalingBible


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
        self.assertEqual(_study_verse_text(bible, 'Psalms', 30, 1, 'hebrew'), '')
        bible.verses.assert_not_called()
        _study_verse_text(bible, 'Psalms', 30, 2, 'hebrew')
        bible.verses.assert_called_once_with(BibleLibBibleBooks.Psalms, 30, 1, 30, 1)

    def test_native_hebrew_translations_are_not_shifted(self):
        bible = Mock()
        bible.name = 'Herziene Statenvertaling'
        bible.abbreviation = 'HSV'
        bible.language = 'nl'
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
