import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase

from walkasjesus_app.lib.bible_api_rate_limit import BibleApiRateLimitExceeded
from walkasjesus_app.lib.strongs_service import (
    search_result_word_study,
    search_strongs_dictionary,
    strongs_occurrence_references,
    strongs_word_detail,
    strongs_word_summary,
    strongs_occurrence_word_detail,
)
from walkasjesus_app.views.bible_study_view import BibleStudySearchView


class ReverseWordStudyTestCase(SimpleTestCase):
    def test_dutch_word_labels_use_local_statenvertaling_not_english_gloss(self):
        summary = strongs_word_summary('H6086', 'nl')
        self.assertEqual(summary['local_gloss'], 'hout')
        self.assertEqual(strongs_word_summary('H6086')['local_gloss'], '')
        dictionary = search_strongs_dictionary('boom', 'nl')
        tree = next(item for item in dictionary if item['strongs_number'] == 'H6086')
        self.assertEqual(tree['local_gloss'], summary['local_gloss'])
        detail = strongs_word_detail('H6086', 'nl')
        self.assertEqual(detail['words'][0]['word_components'][0]['local_gloss'], summary['local_gloss'])

    @patch('walkasjesus_app.lib.strongs_service.localized_original_text_payload')
    def test_occurrence_details_reuse_localized_original_word(self, localized):
        english = strongs_occurrence_word_detail('H0977', 'Job', 7, 15, 0)
        word = dict(english['words'][0], local_gloss='kiest')
        localized.return_value = {'words': [word]}
        dutch = strongs_occurrence_word_detail('H0977', 'Job', 7, 15, 0, language_code='nl')
        self.assertEqual(dutch['words'][0]['local_gloss'], 'kiest')
        self.assertEqual(dutch['words'][0]['text'], english['words'][0]['text'])
        localized.assert_called_once_with('Job', 7, 15, 'nl')

    def test_life_button_occurrence_matches_h2417_detail_not_lemma(self):
        study = self.study('Ezra', 6, 10,
                           'That they may offer sacrifices of sweet savours unto the God of heaven, '
                           'and pray for the life of the king, and of his sons.', 'life')
        candidate = next(item for item in study['candidates'] if item['strongs_number'] == 'H2417')
        occurrence = candidate['matched_occurrences'][0]
        detail = strongs_occurrence_word_detail('H2417', occurrence['book'], occurrence['chapter'],
                                               occurrence['verse'], occurrence['word_index'])
        self.assertEqual(occurrence['text'], detail['words'][0]['text'])
        self.assertNotEqual(occurrence['text'], candidate['lemma'])

    def test_tree_search_links_plural_trees_before_filtering(self):
        study = self.study('Psalms', 104, 16,
                           "The trees of the LORD are full of sap; the cedars of Lebanon, "
                           "which he hath planted;", 'tree')
        self.assertIn('H6086', [item['strongs_number'] for item in study['candidates']])

    def test_tree_dictionary_preserves_matching_lexical_senses(self):
        candidates = search_strongs_dictionary('tree')
        palm = next(item for item in candidates if item['strongs_number'] == 'H5158')
        self.assertEqual(palm['source_strongs_numbers'], ['H5158B'])
        self.assertEqual(strongs_occurrence_references('H5158B'), ['Num.24:6'])
        self.assertGreater(len(strongs_occurrence_references('H5158')), 1)

    def test_life_dictionary_variant_and_actual_verse_form(self):
        candidates = search_strongs_dictionary('life')
        candidate = next(item for item in candidates if item['strongs_number'] == 'H2416')
        self.assertEqual(candidate['source_strongs_number'], 'H2416E')
        dictionary = strongs_word_detail(candidate['source_strongs_number'])
        self.assertTrue(dictionary['words'][0]['word_components'])
        occurrence = strongs_occurrence_word_detail('H2416', 'Genesis', 1, 20, 6)
        word = occurrence['words'][0]
        self.assertEqual(word['gematria_value'], 23)
        self.assertEqual(word['grammar'], 'HAafsa')
        self.assertEqual(word['word_components'][0]['strongs_number'], 'H2416A')
        self.assertEqual(word['word_components'][0]['role'], 'root')
        self.assertTrue(word['grammar_details'])
        self.assertEqual(strongs_word_detail('H2416')['words'][0]['gematria_value'], 18)
        with self.assertRaises(ValueError):
            strongs_occurrence_word_detail('H1980', 'Genesis', 1, 20, 6)

    def study(self, book, chapter, verse, text, query, source='kjv', scoring=False):
        return search_result_word_study([{
            'book': book, 'chapter': chapter, 'verse': verse,
            'text': text, 'reference': f'{book} {chapter}:{verse}',
        }], query, source, scoring)

    def test_hebrew_word_comes_from_the_matching_verse(self):
        payload = self.study('Genesis', 1, 1,
                             'In the beginning God created the heaven and the earth.', 'God')
        self.assertEqual([item['strongs_number'] for item in payload['candidates']], ['H430'])
        self.assertEqual(payload['candidates'][0]['matched_references'], ['Genesis 1:1'])
        self.assertEqual(payload['candidates'][0]['alignment_method'], 'tagged')

    def test_service_prefix_is_not_presented_as_the_root(self):
        payload = self.study('Genesis', 1, 1,
                             'In the beginning God created the heaven and the earth.', 'beginning')
        self.assertEqual([item['strongs_number'] for item in payload['candidates']], ['H7225'])

    def test_new_testament_returns_actual_greek(self):
        payload = self.study('John', 3, 16,
                             'For God so loved the world, that he gave his only begotten Son', 'loved')
        self.assertEqual([item['strongs_number'] for item in payload['candidates']], ['G25'])
        self.assertEqual(payload['candidates'][0]['language'], 'Greek')

    def test_multiple_original_words_are_retained(self):
        payload = search_result_word_study([
            {'book': 'Genesis', 'chapter': 1, 'verse': 1, 'reference': 'Genesis 1:1',
             'text': 'In the beginning God created the heaven and the earth.'},
            {'book': 'John', 'chapter': 3, 'verse': 16, 'reference': 'John 3:16',
             'text': 'For God so loved the world, that he gave his only begotten Son'},
        ], 'God', 'kjv')
        self.assertEqual({item['strongs_number'] for item in payload['candidates']}, {'H430', 'G2316'})

    def test_untagged_english_alignment_is_labeled_as_an_estimate(self):
        payload = self.study('Genesis', 1, 1,
                             'In the beginning God created the heaven and the earth.', 'God', '', True)
        self.assertEqual(payload['candidates'][0]['strongs_number'], 'H430')
        self.assertEqual(payload['candidates'][0]['alignment_method'], 'lexicon')

    def test_dutch_tagged_word_mapping(self):
        payload = self.study('Genesis', 1, 1,
                             'In den beginne schiep God den hemel en de aarde.', 'God', 'svv')
        self.assertEqual([item['strongs_number'] for item in payload['candidates']], ['H430'])

    def test_unsupported_translation_is_explicitly_unaligned(self):
        payload = self.study('Genesis', 1, 1, 'Au commencement Dieu', 'Dieu', '')
        self.assertEqual(payload, {'candidates': [], 'unaligned_results': 1})

    def test_dictionary_accepts_codes_hebrew_and_dutch(self):
        self.assertEqual(search_strongs_dictionary('h0430')[0]['strongs_number'], 'H430')
        self.assertIn('H430', [item['strongs_number'] for item in search_strongs_dictionary('אלהים')])
        self.assertIn('G26', [item['strongs_number'] for item in search_strongs_dictionary('liefde', 'nl')])
        self.assertEqual(search_strongs_dictionary('H999999'), [])

    def test_detail_uses_shared_full_candidate_shape(self):
        payload = strongs_word_detail('H1980', 'nl')
        candidate = payload['words'][0]['candidates'][0]
        self.assertEqual(payload['language_code'], 'hbo')
        for key in ('lexicon_outline', 'usage_outline', 'root_words', 'local_usage', 'definition'):
            self.assertIn(key, candidate)
        self.assertTrue(strongs_word_summary('H430')['lemma'])

    def test_occurrences_and_book_scope(self):
        self.assertIn('Jhn.13:35', strongs_occurrence_references('G26'))
        self.assertIn('2Co.13:14', strongs_occurrence_references('G26', 'kjv'))
        self.assertIn('Php.1:17', strongs_occurrence_references('G26', 'kjv'))
        self.assertEqual(BibleStudySearchView.parse_step_reference('Jhn.13:35'), ('John', 13, 35))
        self.assertTrue(BibleStudySearchView.reference_in_scope('Deu.1:1', 'GEN-DEU'))
        self.assertFalse(BibleStudySearchView.reference_in_scope('Jos.1:1', 'GEN-DEU'))
        self.assertTrue(BibleStudySearchView.reference_in_scope('Tit.1:1', 'TIT'))
        self.assertTrue(BibleStudySearchView.reference_in_scope('Jhn.13:35', 'GEN.1.1-REV.22.21'))
        self.assertFalse(BibleStudySearchView.reference_in_scope('Jhn.13:35', 'JHN.13.1-JHN.13.34'))
        with self.assertRaises(ValueError):
            BibleStudySearchView.reference_in_scope('Tit.1:1', 'TIT-GEN')


class ReverseWordStudyEndpointTestCase(SimpleTestCase):
    @patch('walkasjesus_app.views.bible_study_view.search_result_word_study')
    @patch('walkasjesus_app.views.bible_study_view._api_bible_search_payload')
    def test_complete_word_search_analyzes_later_pages_and_caches_the_snapshot(self, api_search, study):
        verses = [{'id': f'GEN.1.{index}', 'reference': f'Genesis 1:{index}', 'text': 'tree'}
                  for index in range(1, 122)]
        api_search.side_effect = [
            {'data': {'verses': verses[:100], 'total': 121}},
            {'data': {'verses': verses[100:], 'total': 121}},
        ]
        study.return_value = {'candidates': [{
            'strongs_number': 'H6086', 'matched_references': ['Genesis 1:121'],
        }]}
        cache_data = json.dumps([self.bible.id, 'snapshot-tree', 'canonical', 'AUTO', '', 'hebrew', 'en'])
        key = 'bible_study:complete-search:v3:' + hashlib.sha256(cache_data.encode()).hexdigest()
        cache.delete(key)
        self.addCleanup(cache.delete, key)
        with self.settings(DISABLE_CACHE_FOR_DEBUG=False):
            response = self.get(query='snapshot-tree', mode='verses', study_scope='all', limit=10)
            self.assertEqual(response.status_code, 200)
            payload = json.loads(response.content)
            self.assertEqual(len(payload['all_results']), 121)
            self.assertEqual(len(payload['results']), 10)
            self.assertEqual(len(study.call_args.args[0]), 121)
            self.assertEqual([call.args[3] for call in api_search.call_args_list], [0, 100])
            second = self.get(query='snapshot-tree', mode='verses', study_scope='all', limit=50)
            self.assertEqual(json.loads(second.content)['limit'], 50)
            self.assertEqual(api_search.call_count, 2)

    @patch('walkasjesus_app.views.bible_study_view.search_result_word_study')
    @patch('walkasjesus_app.views.bible_study_view._api_bible_search_payload')
    def test_complete_search_rate_limit_is_not_a_partial_success(self, api_search, study):
        verses = [{'id': f'GEN.1.{index}', 'reference': f'Genesis 1:{index}', 'text': 'tree'}
                  for index in range(1, 101)]
        api_search.side_effect = [
            {'data': {'verses': verses}},
            BibleApiRateLimitExceeded('Daily limit reached', 10, 10),
        ]
        with self.settings(DISABLE_CACHE_FOR_DEBUG=True):
            response = self.get(query='tree', mode='verses', study_scope='all')
        self.assertEqual(response.status_code, 429)
        study.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view._record_bible_usage_for_sources')
    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view.strongs_occurrence_references')
    @patch('walkasjesus_app.views.bible_study_view.search_strongs_dictionary')
    def test_dictionary_multiselect_deduplicates_and_labels_every_page(self, dictionary, references, quota, record):
        for index in range(1, 23):
            self.addCleanup(cache.delete, f'bible_study:v1:test-bible:Genesis:1:{index}')
        dictionary.return_value = [
            {'strongs_number': 'H6086', 'lemma': 'tree'},
            {'strongs_number': 'H6196', 'lemma': 'plane tree'},
        ]
        tree_refs = [f'Gen.1:{index}' for index in range(1, 22)]
        plane_refs = ['Gen.1:21', 'Gen.1:22']
        references.side_effect = lambda code, *args: tree_refs if code == 'H6086' else plane_refs
        with self.settings(DISABLE_CACHE_FOR_DEBUG=True):
            response = self.get(query='tree', mode='lexicon', study_scope='all', limit=10)
            payload = json.loads(response.content)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(payload['total'], 21)
            self.assertEqual(payload['selected_strongs'], ['H6086'])
            payload = json.loads(self.get(query='tree', mode='lexicon', study_scope='all',
                                          selected_strongs='H6086,H6196', limit=10).content)
            self.assertEqual(payload['total'], 22)
            self.assertEqual(payload['selected_strongs'], ['H6086', 'H6196'])
            self.assertEqual([item['range_label'] for item in payload['pages']],
                             ['Gen.1:1–Gen.1:10', 'Gen.1:11–Gen.1:20', 'Gen.1:21–Gen.1:22'])
            filtered = json.loads(self.get(query='tree', mode='lexicon', study_scope='all',
                                          selected_strongs='H6196', limit=10).content)
            self.assertEqual(filtered['total'], 2)
            self.assertEqual([item['reference'] for item in filtered['results']], plane_refs)
            self.assertEqual(len(filtered['word_study']['candidates']), 2)
            empty = json.loads(self.get(query='tree', mode='lexicon', study_scope='all',
                                       selected_strongs='', limit=10).content)
            self.assertEqual(empty['total'], 0)
            self.assertEqual(empty['results'], [])
            self.assertEqual(self.get(query='tree', mode='lexicon', study_scope='all',
                                      selected_strongs='H9999').status_code, 400)

    def test_occurrence_details_preserve_verse_morphology(self):
        response = self.get(query='H2416', mode='detail', book='Genesis', chapter=1, verse=20, word_index=6)
        self.assertEqual(response.status_code, 200)
        detail = json.loads(response.content)['detail']
        self.assertEqual(detail['detail_kind'], 'occurrence')
        self.assertEqual(detail['words'][0]['gematria_value'], 23)
        self.assertEqual(self.get(query='H1980', mode='detail', book='Genesis', chapter=1, verse=20, word_index=6).status_code, 400)
        self.assertEqual(self.get(query='H2416', mode='detail', book='Genesis').status_code, 400)

    def setUp(self):
        self.factory = RequestFactory()
        self.bible = SimpleNamespace(id='test-bible', name='Test Bible', abbreviation='KJV', language='en')
        self.bible.verses = lambda *args: 'A verse about love.'
        self.visible = patch('walkasjesus_app.views.bible_study_view.is_bible_id_visible_for_request', return_value=True)
        self.translation = patch('walkasjesus_app.views.bible_study_view.BibleTranslation')
        self.visible.start()
        self.translation.start().return_value.get.return_value = self.bible
        self.addCleanup(self.visible.stop)
        self.addCleanup(self.translation.stop)

    def get(self, **params):
        request = self.factory.get('/bible-study/search/', {'bible_id': self.bible.id, **params})
        request.LANGUAGE_CODE = 'nl'
        return BibleStudySearchView.as_view()(request)

    @patch('walkasjesus_app.views.bible_study_view._api_bible_search_payload')
    def test_dictionary_first_does_not_search_or_fetch_verses(self, api_search):
        with patch.object(self.bible, 'verses') as verses:
            response = self.get(query='G26', mode='lexicon', original_language='greek')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['candidates'][0]['strongs_number'], 'G26')
        self.assertNotIn('results', payload)
        api_search.assert_not_called()
        verses.assert_not_called()

    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    @patch('walkasjesus_app.views.bible_study_view._record_bible_usage_for_sources')
    def test_selection_fetches_only_scoped_occurrences(self, record_usage, quota):
        key = 'bible_study:v1:test-bible:John:13:35'
        cache.delete(key)
        self.addCleanup(cache.delete, key)
        response = self.get(query='G26', mode='strongs', range='JHN', limit=10, original_language='greek')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload['results'])
        self.assertTrue(all(item['id'].startswith('JHN.') for item in payload['results']))
        self.assertTrue(all(item['text'] == 'A verse about love.' for item in payload['results']))
        for item in payload['results']:
            book, chapter, verse = BibleStudySearchView.parse_step_reference(item['reference'])
            self.addCleanup(cache.delete, f'bible_study:v1:test-bible:{book}:{chapter}:{verse}')
        record_usage.assert_called_once()

    def test_invalid_mode_and_code_are_rejected(self):
        self.assertEqual(self.get(query='God', mode='wrong').status_code, 400)
        self.assertEqual(self.get(query='God', mode='strongs').status_code, 400)

    @patch('walkasjesus_app.views.bible_study_view._record_bible_usage_for_sources')
    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota',
           side_effect=BibleApiRateLimitExceeded('Daily limit reached', 10, 10))
    def test_occurrence_quota_failure_is_explicit(self, quota, record_usage):
        with self.settings(DISABLE_CACHE_FOR_DEBUG=True):
            response = self.get(query='G26', mode='strongs', limit=10, original_language='greek')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.content)['error'], 'Daily limit reached')

    @patch('walkasjesus_app.views.bible_study_view._record_bible_usage_for_sources')
    @patch('walkasjesus_app.views.bible_study_view.consume_bible_api_quota')
    def test_unavailable_occurrence_is_not_returned_as_success(self, quota, record_usage):
        with self.settings(DISABLE_CACHE_FOR_DEBUG=True), patch.object(self.bible, 'verses', return_value=''):
            response = self.get(query='G26', mode='strongs', limit=10, original_language='greek')
        self.assertEqual(response.status_code, 502)
        self.assertIn('unavailable', json.loads(response.content)['error'])

    @patch('walkasjesus_app.views.bible_study_view.is_bible_id_visible_for_request', return_value=False)
    def test_dictionary_respects_translation_visibility(self, visible):
        self.assertEqual(self.get(query='G26', mode='lexicon').status_code, 403)

    def test_original_language_default_and_dictionary_filters(self):
        for language, prefixes in [(None, {'H'}), ('hebrew', {'H'}), ('greek', {'G'}), ('both', {'H', 'G'})]:
            with self.subTest(language=language):
                params = {'original_language': language} if language else {}
                response = self.get(query='love', mode='lexicon', limit=50, **params)
                self.assertEqual(response.status_code, 200)
                candidates = json.loads(response.content)['candidates']
                self.assertEqual({item['strongs_number'][0] for item in candidates}, prefixes)
        self.assertEqual(json.loads(self.get(query='G26', mode='lexicon').content)['total'], 0)
        self.assertEqual(self.get(query='G26', mode='strongs').status_code, 400)
        self.assertEqual(self.get(query='love', original_language='invalid').status_code, 400)

    @patch('walkasjesus_app.views.bible_study_view.search_result_word_study')
    @patch('walkasjesus_app.views.bible_study_view._api_bible_search_payload')
    def test_text_only_search_skips_original_word_analysis(self, api_search, study):
        api_search.return_value = {'data': {'total': 1, 'verses': [
            {'id': 'GEN.1.1', 'reference': 'Genesis 1:1', 'text': 'God'},
        ]}}
        response = self.get(query='God', mode='text')
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual(payload['results'][0]['text'], 'God')
        self.assertIsNone(payload['word_study'])
        study.assert_not_called()
        api_search.assert_called_once()

    @patch('walkasjesus_app.views.bible_study_view.search_result_word_study')
    @patch('walkasjesus_app.views.bible_study_view._api_bible_search_payload')
    def test_word_study_filters_languages_without_removing_translated_verses(self, api_search, study):
        api_search.return_value = {'data': {'total': 2, 'verses': [
            {'id': 'GEN.1.1', 'reference': 'Genesis 1:1', 'text': 'God'},
            {'id': 'JHN.3.16', 'reference': 'John 3:16', 'text': 'God'},
        ]}}
        study.return_value = {'candidates': []}
        for language, books in [(None, ['Genesis']), ('hebrew', ['Genesis']), ('greek', ['John']), ('both', ['Genesis', 'John'])]:
            with self.subTest(language=language):
                params = {'original_language': language} if language else {}
                response = self.get(query='God', **params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(json.loads(response.content)['results']), 2)
                self.assertEqual([item['book'] for item in study.call_args.args[0]], books)
