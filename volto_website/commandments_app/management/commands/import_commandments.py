import logging
import os

from django.core.management import BaseCommand
from import_tool import CommandmentImporter

from commandments_app.models import *
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
        if reference.is_primary:
            model_reference = PrimaryBibleReference(commandment_id=commandment_id)
        else:
            model_reference = SecondaryBibleReference(commandment_id=commandment_id)

        model_reference.book = reference.book.name
        model_reference.chapter = reference.start_chapter
        model_reference.verse = reference.start_verse
        model_reference.save()

    def _add_question(self, commandment_id, question):
        question_model = Question(commandment_id=commandment_id)
        question_model.text = question
        question_model.save()

    def _add_media(self, commandment_id, media):
        media_type = media.type.lower().strip()
        if media_type == 'song':
            model_reference = Song(commandment_id=commandment_id)
        elif media_type == 'shortmovie' or media_type == 'movie':
            model_reference = Video(commandment_id=commandment_id)
        elif media_type == 'picture' or media_type == 'drawing':
            model_reference = Image(commandment_id=commandment_id)
        else:
            logging.getLogger().warning(f'Type {media_type} not yet implemented in import command')
            return

        print(f'Adding {media.title}')
        model_reference.title = media.title
        model_reference.url = media.link
        model_reference.author = media.author
        model_reference.is_public = media.is_public
        model_reference.save()

    def _add_commandment(self, commandment):
        try:
            model_commandment = Commandment(id=commandment.id)
            model_commandment.title = commandment.title
            model_commandment.description = commandment.description
            model_commandment.category = CommandmentCategories(commandment.category).name
            model_commandment.save()
            print(f'Added commandment {model_commandment.id}')
            for item in commandment.bible_references:
                self._add_bible_ref(model_commandment.id, item)
            for item in commandment.questions:
                self._add_question(model_commandment.id, item)
            for item in commandment.media:
                self._add_media(model_commandment.id, item)
        except Exception as ex:
            print(f'Failed to import {commandment.id}')


