import json
from unittest import TestCase
from unittest.mock import Mock

from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_books import BibleBooks


class ApiVerseMarkersTest(TestCase):
    def setUp(self):
        self.bible = ApiBible(api_key='test', bible_id='bgt')

    def test_combined_verse_marker_is_read_once(self):
        for separator in ['-', '\u2013', '\u2014']:
            with self.subTest(separator=separator):
                verses = self.bible.extract_verses(
                    BibleBooks.Titus, 1, f'Introduction [1{separator}4] Combined passage. [5] Next verse.',
                )
                self.assertEqual([(v.chapter, v.verse, v.text) for v in verses], [
                    (1, 1, 'Combined passage.'), (1, 5, 'Next verse.'),
                ])
                self.assertEqual([(v.verse, v.end_verse) for v in verses], [(1, 4), (5, 5)])

    def test_each_member_of_a_combined_passage_returns_text(self):
        self.bible.client.get = Mock(return_value=json.dumps({
            'data': {'content': '[1-4] Combined passage.', 'copyright': 'test'},
        }))
        for verse in range(1, 5):
            with self.subTest(verse=verse):
                self.assertEqual(self.bible.verses(BibleBooks.Titus, 1, verse, 1, verse), 'Combined passage.')

    def test_multi_digit_markers_and_editorial_brackets(self):
        verses = self.bible.extract_verses(BibleBooks.Psalms, 77, '[10]Text [note] here. [11] More.')
        self.assertEqual([(v.chapter, v.verse, v.text) for v in verses], [
            (77, 10, 'Text [note] here.'), (77, 11, 'More.'),
        ])

    def test_new_chapter_starts_only_after_a_previous_verse(self):
        verses = self.bible.extract_verses(BibleBooks.John, 1, '[51] End. [1] Start.')
        self.assertEqual([(v.chapter, v.verse) for v in verses], [(1, 51), (2, 1)])

    def test_study_passage_requests_exclude_titles_without_changing_default_verses(self):
        self.bible.client.get = Mock(return_value=json.dumps({
            'data': {'content': '[1] Verse text.', 'copyright': 'test'},
        }))
        self.bible.verses(BibleBooks.Titus, 1, 1, 1, 1)
        self.assertNotIn('include-titles=false', self.bible.client.get.call_args.args[0])
        for fetch in (
            lambda: self.bible.verses(BibleBooks.Titus, 1, 1, 1, 1, include_titles=False),
            lambda: self.bible.passage_verses(BibleBooks.Titus, 1, 1, 1),
            lambda: self.bible.chapter_verses(BibleBooks.Titus, 1, 1),
        ):
            fetch()
            self.assertIn('include-titles=false', self.bible.client.get.call_args.args[0])
