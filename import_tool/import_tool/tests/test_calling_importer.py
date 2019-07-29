from unittest import TestCase

from import_tool.calling_importer import CallingImporter


class TestCallingImporter(TestCase):
    def test_load(self):
        importer = CallingImporter()
        importer.load()
