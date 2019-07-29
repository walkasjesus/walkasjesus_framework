from unittest import TestCase

from bible_lib import BibleBooks

from import_tool.calling_importer import CallingImporter


class TestCallingImporter(TestCase):
    def test_load(self):
        importer = CallingImporter()
        callings = importer.load()

        self.assertEqual('Bekeer u en geloof het evangelie', callings[0].quote)
        self.assertEqual('Wees vruchtbaar', callings[1].quote)

        self.assertEqual(BibleBooks.Matthew, callings[0].bible_references[0].book)
