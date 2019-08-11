from django.core.management import BaseCommand
from translate_tool import PoTranslator


class Command(BaseCommand):
    def handle(self, *args, **options):
        languages = ['nl']

        translator = PoTranslator()

        for language in languages:
            translator.translate('locale/nl/LC_MESSAGES/django.po', 'en', language)
