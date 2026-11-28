import json
import tempfile
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from bible_lib import BibleBooks as BibleLibBibleBooks
from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.simple_cache import SimpleCache
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
    _study_section_headings,
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
    @patch('walkasjesus_app.views.admin.admin_bible_view.chapters_for_book', return_value=range(1, 2))
    @patch('walkasjesus_app.views.admin.admin_bible_view.Services')
    @patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslationMetaData')
    @patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslation')
    def test_numbering_profiles_and_limitations_are_visible_only_to_staff(self, translations, metadata, services, chapters):
        bibles = [
            SimpleNamespace(id='unknown', name='Unknown translation', abbreviation='UNK', language='en'),
            SimpleNamespace(id='hsv', name='Herziene Statenvertaling', abbreviation='HSV', language='nl'),
        ]
        translations.return_value.all.return_value = bibles
        metadata.objects.filter.return_value.exists.return_value = True
        metadata.objects.get.return_value.is_enabled = True
        services.return_value.cache.cache_items_not_persisted = 0
        services.return_value.cache.cache_path = Path('/nonexistent-bible-cache-for-test')
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

    @override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'limited': 5})
    def test_chapter_coverage_reads_disk_and_excludes_expired_and_partial_passages(self):
        bible = ApiBible(api_key='test', bible_id='free')
        bible.name, bible.language, bible.abbreviation = 'Test Bible', 'en', 'TEST'
        limited = ApiBible(api_key='test', bible_id='limited')
        limited.name, limited.language, limited.abbreviation = 'Limited', 'en', 'LIMIT'
        book = BibleLibBibleBooks.Titus
        def payload(content):
            return json.dumps({'data': {'content': content}})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.json'
            server_cache = SimpleCache(path)
            script_cache = SimpleCache(path)
            script_cache.set_value(bible.chapter_passage_url(book, 1, 3), payload('[1] One [2] Two [3] Three'))
            script_cache.set_value(bible.chapter_passage_url(book, 2, 2), payload('[1] One'), ttl_seconds=300)
            entries = json.loads(path.read_text())
            entries[bible.chapter_passage_url(book, 3, 2)] = {
                'value': payload('[1] One [2] Two'), 'expires_at': 1,
            }
            path.write_text(json.dumps(entries))
            request = RequestFactory().get('/admin/bibles/')
            request.user = SimpleNamespace(is_active=True, is_staff=True)
            request.session = {}
            with patch('walkasjesus_app.views.admin.admin_bible_view.Services') as services, \
                    patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslation') as translations, \
                    patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslationMetaData') as metadata, \
                    patch('walkasjesus_app.views.admin.admin_bible_view._CANONICAL_CHAPTER_COUNTS', {'Titus': 3}), \
                    patch('walkasjesus_app.views.admin.admin_bible_view.chapters_for_book', return_value=range(1, 4)), \
                    patch('walkasjesus_app.views.admin.admin_bible_view.max_display_verse', return_value=2):
                services.return_value.cache = server_cache
                translations.return_value.all.return_value = [bible, limited]
                metadata.objects.filter.return_value.exists.return_value = True
                metadata.objects.get.return_value.is_enabled = True
                response = AdminBibleView.as_view()(request)
                self.assertContains(response, '1 / 3 (33.3%)')
                self.assertIsNone(limited.percentage_cached)
                script_cache.set_value(bible.chapter_passage_url(book, 2, 2), payload('[1] One [2] Two'))
                response = AdminBibleView.as_view()(request)
                self.assertContains(response, '2 / 3 (66.7%)')

    def test_chapter_coverage_accepts_larger_passages_and_requires_all_source_chapters(self):
        bible = ApiBible(api_key='test', bible_id='free')
        entry = {'value': json.dumps({'data': {'content': '[1] One [2] Two [3] Three'}})}
        passages = {'TIT': [(1, entry)]}
        with patch('walkasjesus_app.views.admin.admin_bible_view.max_display_verse', return_value=2), \
                patch('walkasjesus_app.views.admin.admin_bible_view._study_verse_references',
                      side_effect=lambda bible, book, chapter, verse, system: ([(verse, 1)], (), '')):
            view = AdminBibleView()
            self.assertEqual(view.bible_count_in_cache(bible, passages, {'Titus': [1]}), 0)
            passages['TIT'].append((2, entry))
            self.assertEqual(view.bible_count_in_cache(bible, passages, {'Titus': [1]}), 1)

    def test_chapter_coverage_shows_error_for_unreadable_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cache.json'
            path.write_text('{')
            with patch('walkasjesus_app.views.admin.admin_bible_view.Services') as services, \
                    patch('walkasjesus_app.views.admin.admin_bible_view.BibleTranslation') as translations, \
                    patch('walkasjesus_app.views.admin.admin_bible_view.chapters_for_book', return_value=range(1, 2)):
                services.return_value.cache.cache_path = path
                services.return_value.cache.cache_items_not_persisted = 0
                translations.return_value.all.return_value = []
                request = RequestFactory().get('/admin/bibles/')
                request.user = SimpleNamespace(is_active=True, is_staff=True)
                request.session = {}
                with self.assertLogs('walkasjesus_app.views.admin.admin_bible_view', level='WARNING'):
                    response = AdminBibleView.as_view()(request)
                self.assertContains(response, 'The chapter cache could not be read.')


class PsalmVersificationTest(SimpleTestCase):
    def test_indexed_english_references_match_source_rows(self):
        from walkasjesus_app.lib.strongs_service import (
            _stepbible_book_code, _stepbible_file_for_book, _step_reference_to_display,
        )
        for book, chapter, verse in [('John', 3, 1), ('Psalms', 30, 1), ('Hosea', 2, 1)]:
            with self.subTest(book=book):
                code = _stepbible_book_code(book)
                expected_reference = f'{code}.{chapter}:{verse}'
                with _stepbible_file_for_book(book).open(encoding='utf-8') as file:
                    expected = [
                        line.rstrip('\n') for line in file
                        if line.startswith(f'{code}.{chapter}.{verse}')
                        and '#' in line
                        and _step_reference_to_display(line.partition('#')[0]) == expected_reference
                    ]
                self.assertTrue(expected)
                self.assertEqual(_stepbible_rows_for_verse(book, chapter, verse), expected)

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

    def test_naardense_joel_uses_provider_hebrew_chapters_not_kjv_chapters(self):
        bible = Mock()
        bible.name = 'Naardense Bijbel 2024'
        bible.language = 'nl'
        bible.abbreviation = 'NAB2024'
        bible.verses.return_value = 'Provider source text.'
        for chapter, verse in ((2, 27), (3, 1), (3, 5), (4, 1), (4, 21)):
            with self.subTest(chapter=chapter, verse=verse):
                self.assertEqual(
                    _study_verse_references(bible, 'Joel', chapter, verse, 'hebrew'),
                    (((chapter, verse),), ((chapter, verse),), ''),
                )
                _study_verse_text(bible, 'Joel', chapter, verse, 'hebrew')
                bible.verses.assert_called_with(BibleLibBibleBooks.Joel, chapter, verse, chapter, verse)

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
        sections = patch(
            'walkasjesus_app.views.bible_study_view.requests.get', return_value=Mock(status_code=404))
        self.section_network = sections.start()
        self.addCleanup(sections.stop)

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    @override_settings(DISABLE_CACHE_FOR_DEBUG=False)
    def test_api_errors_are_not_cached_as_verse_text(self, translations, _quota):
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        parameters = {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1,
            'start_verse': 1, 'end_verse': 1, 'reference_system': 'hebrew',
        }
        for endpoint in ('commandments:bible_study', 'commandments:bible_study_verses'):
            with self.subTest(endpoint=endpoint):
                cache.clear()
                with patch('walkasjesus_app.views.bible_study_view._fetch_licensed_passage',
                           return_value=({}, {}, {})), \
                        patch('walkasjesus_app.views.bible_study_view._fetch_chapter_verse_texts',
                              return_value={}), \
                        patch.object(self.bible, 'verses', side_effect=['Not found', 'Verse text.']):
                    if endpoint == 'commandments:bible_study':
                        first = self.client.get(reverse(endpoint), parameters)
                        second = self.client.get(reverse(endpoint), parameters)
                        first_text = first.context['selected_bibles'][0]['verse_texts']['1']
                        second_text = second.context['selected_bibles'][0]['verse_texts']['1']
                    else:
                        first = self.client.post(reverse(endpoint), parameters)
                        second = self.client.post(reverse(endpoint), parameters)
                        first_text = first.json()['verses']['1']
                        second_text = second.json()['verses']['1']
                self.assertEqual(first_text, '')
                self.assertEqual(second_text, 'Verse text.')

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
    @override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'bgt': 5}, DISABLE_CACHE_FOR_DEBUG=False)
    def test_titus_bgt_combined_verses_are_not_empty(self, translations, _quota):
        translations.return_value.get.return_value = self.bible
        self.bible.client.get = Mock(return_value=json.dumps({
            'data': {'content': '[1-4] Combined passage. [5] Next verse.', 'copyright': 'test'},
        }))
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 5,
            'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses'], {
            '1': 'Combined passage.', '2': 'Combined passage.', '3': 'Combined passage.',
            '4': 'Combined passage.', '5': 'Next verse.',
        })
        self.assertEqual(response.json()['verse_references'], {
            '1': '1:1-4', '2': '1:1-4', '3': '1:1-4', '4': '1:1-4', '5': '1:5',
        })
        self.bible.client.get.assert_called_once()

        self.bible.client.get.reset_mock()
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 5,
            'reference_system': 'hebrew',
        })
        self.assertEqual(response.json()['verse_references']['3'], '1:1-4')
        self.assertEqual(set(response.json()['verse_sources'].values()), {'cache'})
        self.bible.client.get.assert_not_called()
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        response = self.client.get(reverse('commandments:bible_study'), {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 5,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_bibles'][0]['verse_references']['4'], '1:1-4')
        self.bible.client.get.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    @override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'bgt': 5})
    def test_bgt_range_starting_inside_merged_verses_keeps_complete_group(self, translations, _quota):
        translations.return_value.get.return_value = self.bible
        self.bible.client.get = Mock(return_value=json.dumps({
            'data': {'content': '[1–4] Combined passage. [5] Next verse.', 'copyright': 'test'},
        }))
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 2, 'end_verse': 5,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses']['2'], 'Combined passage.')
        self.assertEqual(response.json()['verse_references']['2'], '1:1-4')
        self.assertNotIn('1', response.json()['verses'])
        self.assertIn('TIT.1.2-TIT.1.5?', self.bible.client.get.call_args.args[0])

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
        verses.assert_called_once_with(BibleLibBibleBooks.Psalms, 30, 1, 30, 1, include_titles=False)
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
        verses.assert_called_once_with(BibleLibBibleBooks.Hosea, 1, 12, 1, 12, include_titles=False)

    @patch('walkasjesus_app.views.bible_study_view.localized_original_text_payload')
    def test_original_endpoint_passes_hebrew_numbering(self, original):
        original.return_value = {'sentence': 'Title'}
        response = self.client.post(reverse('commandments:bible_study_original_text'), {
            'book': 'Psalms', 'chapter': 30, 'start_verse': 1,
            'end_verse': 1, 'reference_system': 'hebrew',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(original.call_args.kwargs['reference_system'], 'hebrew')

    @patch('walkasjesus_app.views.bible_study_view.localized_original_text_payload')
    def test_original_endpoint_compacts_repeated_references_without_losing_groups(self, original):
        refs = [f'Gen.1:{i}' for i in range(1, 13)]
        groups = [refs[:2], refs[2:5], refs[5:9], refs[9:]]
        original.return_value = {
            'words': [{'references': refs, 'reference_groups': groups}, {'references': refs}],
            'selected_word': {'references': refs},
        }
        data = {'book': 'Genesis', 'chapter': 1, 'start_verse': 1, 'end_verse': 1}
        url = reverse('commandments:bible_study_original_text')
        legacy = self.client.post(url, data).json()
        compact = self.client.post(url, {**data, 'compact_references': '1'}).json()
        self.assertNotIn('reference_lists', legacy)
        self.assertEqual(compact['reference_lists'], [refs])
        word = compact['verses']['1']['words'][0]
        self.assertEqual(word['references'], {'$refs': 0})
        self.assertEqual(word['reference_groups'], {'$refs': 0, 'groups': [2, 3, 4, 3]})
        self.assertEqual(compact['verses']['1']['selected_word']['references'], {'$refs': 0})
        self.assertEqual(legacy['verses']['1'], original.return_value)

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

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    @override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'bgt': 5}, DISABLE_CACHE_FOR_DEBUG=False)
    def test_combined_sections_are_scoped_cached_and_in_initial_page_payload(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        self.bible.client.get = Mock(return_value=json.dumps({
            'data': {'content': '[1-4] Combined passage. [5] Next verse.', 'copyright': 'test'},
        }))
        self.section_network.return_value = Mock(status_code=200, json=Mock(return_value={'data': [
            {'id': 'TIT.S1', 'title': 'First <heading>', 'firstVerseId': 'TIT.1.1', 'lastVerseId': 'TIT.1.4'},
            {'id': 'TIT.S2', 'title': 'Next heading', 'firstVerseId': 'TIT.1.5', 'lastVerseId': 'TIT.2.3'},
            {'id': 'TIT.S3', 'title': 'Unrelated heading', 'firstVerseId': 'TIT.1.6', 'lastVerseId': 'TIT.1.9'},
        ]}))
        parameters = {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 2, 'end_verse': 5,
            'reference_system': 'hebrew', 'combine_verses': '1',
        }
        response = self.client.post(reverse('commandments:bible_study_verses'), parameters)
        self.assertEqual(response.status_code, 200)
        expected = [
            {'id': 'TIT.S1', 'title': 'First <heading>', 'verse': 2},
            {'id': 'TIT.S2', 'title': 'Next heading', 'verse': 5},
        ]
        self.assertEqual(response.json()['sections'], expected)
        self.assertEqual(response.json()['verses']['2'], 'Combined passage.')
        self.assertEqual(quota.call_count, 2)
        self.assertIn('include-titles=false', self.bible.client.get.call_args.args[0])
        self.section_network.assert_called_once()
        response = self.client.post(reverse('commandments:bible_study_verses'), parameters)
        self.assertEqual(response.json()['sections'], expected)
        self.section_network.assert_called_once()
        self.assertEqual(quota.call_count, 2)
        response = self.client.get(reverse('commandments:bible_study'), parameters)
        self.assertEqual(response.context['selected_bibles'][0]['sections'], expected)
        self.assertContains(response, 'First \\u003Cheading\\u003E')
        self.assertNotContains(response, 'First <heading>')
        self.section_network.assert_called_once()
        response = self.client.post(
            reverse('commandments:bible_study_verses'), {**parameters, 'combine_verses': '0'})
        self.assertEqual(response.json()['sections'], [])
        self.section_network.assert_called_once()
        headings, warning = _study_section_headings(
            self.bible, 'Titus', 2, [1, 2], 'english', RequestFactory().get('/'), 'verses_api')
        self.assertEqual(headings, [{'id': 'TIT.S2', 'title': 'Next heading', 'verse': 1}])
        self.assertEqual(warning, '')
        self.section_network.assert_called_once()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @override_settings(DISABLE_CACHE_FOR_DEBUG=False)
    def test_sections_use_source_references_for_hebrew_cross_chapter_mapping(self, quota):
        self.bible.name = 'King James Version'
        self.section_network.return_value = Mock(status_code=200, json=Mock(return_value={'data': [
            {'id': 'JOL.S1', 'title': 'Heading', 'firstVerseId': 'JOL.2.28', 'lastVerseId': 'JOL.3.21'},
        ]}))
        headings, warning = _study_section_headings(
            self.bible, 'Joel', 3, [1, 2, 3], 'hebrew', RequestFactory().get('/'),
            'verses_api',
        )
        self.assertEqual(headings, [{'id': 'JOL.S1', 'title': 'Heading', 'verse': 1}])
        self.assertEqual(warning, '')
        self.assertIn('/books/JOL/sections', self.section_network.call_args.args[0])
        quota.assert_called_once()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_heading_checkbox_gates_page_and_ajax_and_keeps_disabled_selection(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        translations.return_value.all_in_supported_languages.return_value = [self.bible]
        parameters = {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 1,
            'combine_verses': '1', 'show_sections': '0',
        }
        with patch.object(self.bible, 'verses', return_value='Verse text.'), \
                patch('walkasjesus_app.views.bible_study_view._study_section_headings') as sections:
            response = self.client.get(reverse('commandments:bible_study'), parameters)
            self.assertFalse(response.context['show_sections'])
            self.assertEqual(response.context['selected_bibles'][0]['sections'], [])
            self.assertContains(response, 'id="bs-show-sections" name="show_sections" value="1">')
            response = self.client.post(reverse('commandments:bible_study_verses'), parameters)
            self.assertEqual(response.json()['sections'], [])
            self.assertEqual(response.json()['section_warning'], '')
            response = self.client.get(
                reverse('commandments:bible_study'), {**parameters, 'combine_verses': '0', 'show_sections': '1'})
            self.assertTrue(response.context['show_sections'])
            self.assertFalse(response.context['combine_verses'])
            self.assertContains(response, 'id="bs-show-sections" name="show_sections" value="1" checked disabled>')
            response = self.client.post(
                reverse('commandments:bible_study_verses'), {**parameters, 'combine_verses': '0', 'show_sections': '1'})
            self.assertEqual(response.json()['sections'], [])
            sections.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @override_settings(DISABLE_CACHE_FOR_DEBUG=False)
    def test_sections_absence_is_cached_and_local_translations_do_not_fetch(self, quota):
        arguments = (self.bible, 'Titus', 1, [1, 2], 'english', RequestFactory().get('/'), 'verses_api')
        for _ in range(2):
            self.assertEqual(_study_section_headings(*arguments), ([], ''))
        self.section_network.assert_called_once()
        quota.assert_called_once()
        self.assertEqual(_study_section_headings(
            LocalStatenvertalingBible('svv-statenvertaling'), *arguments[1:]), ([], ''))
        self.section_network.assert_called_once()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    @override_settings(DISABLE_CACHE_FOR_DEBUG=False)
    def test_section_failures_preserve_verses_and_can_be_retried(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        parameters = {
            'bible_id': 'bgt', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 1,
            'combine_verses': '1',
        }
        with patch.object(self.bible, 'verses', return_value='Verse text.'), \
                self.assertLogs('walkasjesus_app.views.bible_study_view', level='ERROR'):
            self.section_network.side_effect = requests.Timeout('Metadata timeout')
            response = self.client.post(reverse('commandments:bible_study_verses'), parameters)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses'], {'1': 'Verse text.'})
        self.assertTrue(response.json()['section_warning'])
        self.section_network.side_effect = None
        response = self.client.post(reverse('commandments:bible_study_verses'), parameters)
        self.assertEqual(response.json()['section_warning'], '')
        self.assertEqual(self.section_network.call_count, 2)

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    def test_invalid_section_references_are_explicitly_reported(self, quota):
        self.section_network.return_value = Mock(status_code=200, json=Mock(return_value={'data': [
            {'id': 'TIT.S1', 'title': 'Heading', 'firstVerseId': 'INVALID', 'lastVerseId': 'TIT.1.5'},
        ]}))
        with self.assertLogs('walkasjesus_app.views.bible_study_view', level='ERROR'):
            headings, warning = _study_section_headings(
                self.bible, 'Titus', 1, [1], 'english', RequestFactory().get('/'), 'verses_api')
        self.assertEqual(headings, [])
        self.assertTrue(warning)


@override_settings(BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID={'nbv21': 5})
class BibleStudyChapterDisplayTest(TestCase):
    """Whole-chapter display for unrestricted translations and license limit enforcement."""

    def setUp(self):
        cache.clear()
        self.bible = ApiBible(api_key='test', bible_id='free')
        self.bible.name = 'Naardense Bijbel'
        self.bible.language = 'nl'

    def test_effective_max_verses_uses_strictest_license_limit(self):
        from walkasjesus_app.lib.bible_display_limits import effective_max_verses, max_verses_for_bible_id
        self.assertEqual(max_verses_for_bible_id('nbv21'), 5)
        self.assertIsNone(max_verses_for_bible_id('free'))
        self.assertEqual(effective_max_verses(['free', 'nbv21']), 5)
        self.assertEqual(effective_max_verses(['free']), 200)
        self.assertEqual(effective_max_verses([]), 200)

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_license_limited_translation_is_clamped_server_side(self, translations, quota):
        limited = ApiBible(api_key='test', bible_id='nbv21')
        limited.name = 'NBV21'
        limited.language = 'nl'
        translations.return_value.get.return_value = limited
        limited.client.get = Mock(return_value=json.dumps({
            'data': {'content': ' '.join(f'[{v}] Verse {v}.' for v in range(1, 6)), 'copyright': 'test'},
        }))
        with patch.object(limited, 'chapter_verses') as chapter_fetch:
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'nbv21', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 16,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.json()['verses'], key=int), ['1', '2', '3', '4', '5'])
        self.assertIn('TIT.1.1-TIT.1.5?', limited.client.get.call_args.args[0])
        chapter_fetch.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_whole_chapter_uses_single_passage_request_and_seeds_cache(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        content = ' '.join(f'[{v}] Verse {v}.' for v in range(1, 17))
        self.bible.client.get = Mock(return_value=json.dumps({'data': {'content': content, 'copyright': 'test'}}))
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'free', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 16,
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['verses']['1'], 'Verse 1.')
        self.assertEqual(payload['verses']['16'], 'Verse 16.')
        self.assertEqual(set(payload['verse_sources'].values()), {'api'})
        self.bible.client.get.assert_called_once()
        quota.assert_called_once()

        # Second request is served entirely from the seeded per-verse cache.
        self.bible.client.get.reset_mock()
        response = self.client.post(reverse('commandments:bible_study_verses'), {
            'bible_id': 'free', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 16,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()['verse_sources'].values()), {'cache'})
        self.bible.client.get.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
    def test_failed_chapter_fetch_falls_back_to_per_verse_requests(self, translations, quota):
        translations.return_value.get.return_value = self.bible
        with patch.object(self.bible, 'chapter_verses', side_effect=Exception('boom')), \
                patch.object(self.bible, 'verses', return_value='Fallback verse.') as verses:
            response = self.client.post(reverse('commandments:bible_study_verses'), {
                'bible_id': 'free', 'book': 'Titus', 'chapter': 1, 'start_verse': 1, 'end_verse': 16,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['verses']['16'], 'Fallback verse.')
        self.assertEqual(verses.call_count, 16)

    def test_prefetch_command_skips_license_limited_and_local_translations(self):
        from walkasjesus_app.management.commands.prefetch_bible_chapters import Command
        limited = ApiBible(api_key='test', bible_id='nbv21')
        limited.name = 'NBV21'
        local = SimpleNamespace(id='svv', name='SVV', is_local_source=True)
        output = StringIO()
        with patch('walkasjesus_app.management.commands.prefetch_bible_chapters.BibleTranslation') as translations:
            translations.return_value.all_in_supported_languages.return_value = [self.bible, limited, local]
            command = Command(stdout=output)
            eligible = command._target_bibles(None)
        self.assertEqual([bible.id for bible in eligible], ['free'])
        self.assertIn('Skipping NBV21 (nbv21)', output.getvalue())

    @override_settings(BIBLE_PREFETCH_BIBLE_IDS=[])
    def test_prefetch_default_and_explicit_translation_order(self):
        from walkasjesus_app.management.commands.prefetch_bible_chapters import Command

        def bible(bible_id, name, language):
            return SimpleNamespace(id=bible_id, name=name, language=language, chapter_verses=Mock())

        other = bible('other', 'Other', 'en')
        messianic = bible('wmb', 'World Messianic Bible', 'en')
        kjv = bible('de4e12af7f28f599-01', 'King James Version', 'en')
        dutch = bible('nl', 'Nederlandse Bijbel', 'nl')
        with patch('walkasjesus_app.management.commands.prefetch_bible_chapters.BibleTranslation') as translations:
            translations.return_value.all_in_supported_languages.return_value = [other, messianic, kjv, dutch]
            translations.return_value.get.side_effect = {b.id: b for b in [other, messianic, kjv, dutch]}.get
            command = Command()
            self.assertEqual([b.id for b in command._target_bibles(None)],
                             ['nl', kjv.id, 'wmb', 'other'])
            self.assertEqual([b.id for b in command._target_bibles(['wmb', 'nl'])], ['wmb', 'nl'])
            with override_settings(BIBLE_PREFETCH_BIBLE_IDS=['other', 'nl']):
                self.assertEqual([b.id for b in command._target_bibles(None)], ['other', 'nl'])

    def test_prefetch_respects_book_order_and_logs_translation(self):
        from walkasjesus_app.management.commands.prefetch_bible_chapters import Command
        self.bible.name = 'Test Translation'
        output = StringIO()
        with patch.object(Command, '_target_bibles', return_value=[self.bible]), \
                patch('walkasjesus_app.management.commands.prefetch_bible_chapters.chapters_for_book', return_value=[1]), \
                patch('walkasjesus_app.management.commands.prefetch_bible_chapters.max_display_verse', return_value=1), \
                patch('walkasjesus_app.management.commands.prefetch_bible_chapters._study_chapter_source_plan',
                      return_value=({1: [(1, 1)]}, {1: 1})), \
                patch('walkasjesus_app.management.commands.prefetch_bible_chapters.Services') as services:
            services.return_value.cache.expires_at.return_value = None
            services.return_value.cache.cache_items_not_persisted = 0
            call_command('prefetch_bible_chapters', books=['John', 'Genesis'],
                         max_requests=2, dry_run=True, stdout=output)
        log = output.getvalue()
        self.assertIn('Test Translation (free): would refresh John 1', log)
        self.assertLess(log.index('John 1'), log.index('Genesis 1'))

    def test_prefetch_second_run_skips_persisted_chapter_and_advances(self):
        from walkasjesus_app.management.commands.prefetch_bible_chapters import Command
        self.bible.name = 'Test Translation'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'api-cache.json'
            other_process = SimpleCache(path)
            output = StringIO()

            def fetch(bible, book, chapter, verses, reference_system, force_refresh):
                current_cache.set_value(bible.chapter_passage_url(BibleLibBibleBooks.Titus, chapter, 1), 'text')
                return {1: 'text'}

            with patch.object(Command, '_target_bibles', return_value=[self.bible]), \
                    patch('walkasjesus_app.management.commands.prefetch_bible_chapters.chapters_for_book',
                          return_value=[1, 2]), \
                    patch('walkasjesus_app.management.commands.prefetch_bible_chapters.max_display_verse',
                          return_value=1), \
                    patch('walkasjesus_app.management.commands.prefetch_bible_chapters._study_chapter_source_plan',
                          side_effect=lambda bible, book, chapter, verses, system: ({}, {chapter: 1})), \
                    patch('walkasjesus_app.management.commands.prefetch_bible_chapters._fetch_chapter_verse_texts',
                          side_effect=fetch), \
                    patch('walkasjesus_app.management.commands.prefetch_bible_chapters.Services') as services:
                current_cache = SimpleCache(path)
                services.return_value.cache = current_cache
                call_command('prefetch_bible_chapters', books=['Titus'], max_requests=1, sleep=0, stdout=output)
                other_process.set_value('unrelated', 'value')
                current_cache = SimpleCache(path)
                services.return_value.cache = current_cache
                call_command('prefetch_bible_chapters', books=['Titus'], max_requests=1, sleep=0, stdout=output)
            self.assertIn('skipped Titus 1 (cache still valid)', output.getvalue())
            self.assertIn('refreshed Titus 2', output.getvalue())

    def test_prefetch_rejects_unknown_book(self):
        from walkasjesus_app.management.commands.prefetch_bible_chapters import Command
        with patch.object(Command, '_target_bibles', return_value=[self.bible]):
            with self.assertRaisesRegex(CommandError, 'Unknown Bible book.*NotABook'):
                call_command('prefetch_bible_chapters', books=['NotABook'], stdout=StringIO())

    def test_chapter_verses_parses_passage_content(self):
        content = '[1] In the beginning. [2] And the earth. [3] And God said.'
        self.bible.client.get = Mock(return_value=json.dumps({'data': {'content': content, 'copyright': 'test'}}))
        mapping = self.bible.chapter_verses(BibleLibBibleBooks.Genesis, 1, 3)
        self.assertEqual(mapping, {1: 'In the beginning.', 2: 'And the earth.', 3: 'And God said.'})
