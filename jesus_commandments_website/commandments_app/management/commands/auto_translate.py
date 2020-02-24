import os

from django.core.management import BaseCommand
from translate_tool import PoTranslator

from jesus_commandments_website.settings import BASE_DIR, LANGUAGES


class Command(BaseCommand):
    def handle(self, *args, **options):
        languages = [code for code, name in LANGUAGES]

        translator = PoTranslator()

        for language in languages:
            if language != 'en':
                file_path = os.path.join(BASE_DIR, 'translations', 'locale', language, 'LC_MESSAGES', 'django.po')
                translator.translate(file_path, 'en', language)
