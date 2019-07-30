import os

from django.core.management import BaseCommand
from import_tool import CommandmentImporter
from commandments_app.models import Commandment, SecondaryBibleReference
from volto_website.settings import BASE_DIR


class Command(BaseCommand):
    def handle(self, *args, **options):
        file_path = os.path.join(BASE_DIR, 'data', 'commandments.csv')
        importer = CommandmentImporter()
        commandments = importer.load(file_path)

        print('Adding %s commandments' % len(commandments))
        for item in commandments:
            self._add_commandment(item)

    def _add_bible_ref(self, commandment_id, reference):
        model_reference = SecondaryBibleReference(commandment_id=commandment_id)
        model_reference.book = reference.book.name
        model_reference.chapter = reference.start_chapter
        model_reference.verse = reference.start_verse
        model_reference.save()

    def _add_commandment(self, commandment):
        model_commandment = Commandment()
        model_commandment.title = commandment.title
        model_commandment.save()
        print(f'Added commandment {model_commandment.id}')
        for ref in commandment.bible_references:
            self._add_bible_ref(model_commandment.id, ref)
