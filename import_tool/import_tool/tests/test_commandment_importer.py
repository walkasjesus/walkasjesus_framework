from unittest import TestCase

from bible_lib import BibleBooks

from import_tool.commandment_importer import CommandmentImporter


class TestCommandmentImporter(TestCase):
    def test_load(self):
        importer = CommandmentImporter()
        commandments = importer.load()

        self.assertEqual('Bekeer u en geloof het evangelie', commandments[0].quote)
        self.assertEqual('Wees vruchtbaar', commandments[1].quote)

        self.assertEqual(BibleBooks.Matthew, commandments[0].bible_references[0].book)
