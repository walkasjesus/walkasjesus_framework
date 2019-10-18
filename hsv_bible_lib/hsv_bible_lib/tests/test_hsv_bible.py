from pathlib import Path
from unittest import TestCase
from bible_lib import BibleBooks

from hsv_bible_lib.bible_hsv.hsv_bible import HsvBible

key = Path('key').open().read()
bible_path = Path('path').open().read()


class TestHsvBible(TestCase):
    def test_load(self):
        bible = HsvBible(key, bible_path)

        self.assertEqual('hsv', bible.id)
        self.assertNotEqual(None, bible._content)

    def test_verse(self):
        bible = HsvBible(key, bible_path)
        text = bible.verse(BibleBooks.Mark, 2, 5)
        self.assertEqual('En toen Jezus hun geloof zag, zei Hij tegen de verlamde: Zoon, uw zonden zijn u vergeven.',
                         text)

    def test_verses(self):
        bible = HsvBible(key, bible_path)
        text = bible.verses(BibleBooks.Proverbs, 14, 35, 15, 1)
        self.assertEqual(
            'Aan een verstandige dienaar heeft de koning een welgevallen, maar zijn verbolgenheid treft hem die beschaamd maakt. Een zacht antwoord keert woede af, maar een krenkend woord wekt toorn op.',
            text)
