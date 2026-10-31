import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from bible_lib.bible_api.api_bible import ApiBible
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from walkasjesus_app.views.bible_study_view import (
    _CANONICAL_CHAPTER_COUNTS,
    _load_chapter_index,
    _primary_chapter_index_bible_id,
)


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
