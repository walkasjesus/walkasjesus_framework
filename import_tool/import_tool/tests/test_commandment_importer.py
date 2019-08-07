from unittest import TestCase

from bible_lib import BibleBooks

from import_tool.commandment_importer import CommandmentImporter


class TestCommandmentImporter(TestCase):
    def test_load(self):
        importer = CommandmentImporter()
        commandments = importer.load()

        self.assertEqual('Repent and believe the gospel', commandments[0].title)
        self.assertEqual('Be fruitful', commandments[1].title)

        self.assertEqual(BibleBooks.Matthew, commandments[0].bible_references[0].book)
