from unittest import TestCase
import polib
from google_trans import Translator


class TestTranslater(TestCase):
    def test_translate(self):
        translator = Translator()
        translation = translator.translate('Welcome on this website', src='en', dest='nl')

        self.assertEqual('Welkom op deze website', translation.text)
