import os

from django.core.management import BaseCommand
from django.db import IntegrityError
from import_tool import MediaImporter

from commandments_app.models import *
from jesus_commandments_website.settings import BASE_DIR


class Command(BaseCommand):
    def handle(self, *args, **options):
        file_path = os.path.join(BASE_DIR, 'data', 'media', 'media.csv')
        importer = MediaImporter()
        commandments = importer.load(file_path)

        print('Adding %s commandments' % len(commandments))
        for item in commandments:
            self._add_commandment(item)

    def _add_media(self, commandment_id, media):
        media_type = media.type.lower().strip()
        if media_type == 'song':
            model_reference = Song(commandment_id=commandment_id)
        elif media_type == 'superbook':
            model_reference = Superbook(commandment_id=commandment_id)
        elif media_type == 'movie':
            model_reference = Movie(commandment_id=commandment_id)
        elif media_type == 'shortmovie':
            model_reference = ShortMovie(commandment_id=commandment_id)
        elif media_type == 'drawing':
            model_reference = Drawing(commandment_id=commandment_id)
        elif media_type == 'testimony':
            model_reference = Testimony(commandment_id=commandment_id)
        elif media_type == 'blog':
            model_reference = Blog(commandment_id=commandment_id)
        elif media_type == 'picture':
            model_reference = Picture(commandment_id=commandment_id)
        elif media_type == 'sermon':
            model_reference = Sermon(commandment_id=commandment_id)
        elif media_type == 'book':
            model_reference = Book(commandment_id=commandment_id)
        else:
            logging.getLogger().warning(f'Type {media_type} not yet implemented in import command')
            return

        model_reference.title = media.title
        model_reference.description = media.description
        model_reference.target_audience = media.target_audience
        model_reference.language = media.language
        model_reference.img_url = media.img_url
        model_reference.url = media.url
        model_reference.author = media.author
        model_reference.is_public = media.is_public
        self._save(model_reference)

    def _add_commandment(self, commandment):
        try:
            model_commandment, is_new = Commandment.objects.get_or_create(id=commandment.id)
            model_commandment.save()

            if is_new:
                print(f'Added commandment {model_commandment.id}')
            else:
                print(f'Updating commandment {model_commandment.id}')

            for item in commandment.media:
                self._add_media(model_commandment.id, item)
        except Exception as ex:
            print(ex)
            print(f'Failed to import {commandment.id}')

    def _save(self, model_object):
        try:
            model_object.save()
            print(f'Added {model_object}.')
        except IntegrityError:
            print(f'Skipped {model_object} as it already exists.')
        except Exception as ex:
            print(f'Failed inserting {model_object} with error {ex}.')
