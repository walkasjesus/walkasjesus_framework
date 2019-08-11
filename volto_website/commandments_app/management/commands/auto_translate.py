import os

from django.core.management import BaseCommand
from translate_tool import PoTranslator

from volto_website.settings import BASE_DIR


class Command(BaseCommand):
    def handle(self, *args, **options):
        languages = ['nl']

        translator = PoTranslator()

        for language in languages:
            file_path = os.path.join(BASE_DIR, 'locale', language, 'LC_MESSAGES', 'django.po')
            translator.translate(file_path, 'en', language)
