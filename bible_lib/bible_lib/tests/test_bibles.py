from unittest import TestCase

from bibles import Bibles


class TestBibles(TestCase):
    def test_list_bibles(self):
        bibles = Bibles()
        bible_list = bibles.list()
        
        self.assertTrue(1)