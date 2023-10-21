import os

from django.core.management import BaseCommand
from django.db import IntegrityError
from import_tool import LessonMediaImporter

from commandments_app.models import *
from jesus_commandments_website.settings import BASE_DIR


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='The file name and path to read the data from.')

    def handle(self, *args, **options):
        if 'source' in options:
            file_path = options['source']
        else:
            file_path = os.path.join(BASE_DIR, 'data', 'media', 'media_lessons.csv')

        importer = LessonMediaImporter()
        lessons = importer.load(file_path)

        print('Adding %s lessons' % len(lessons))
        for item in lessons:
            self._add_lesson(item)

    def _add_media(self, lesson_id, media):
        media_type = media.type.lower().strip()
        if media_type == 'song':
            model_reference = LessonSong(lesson_id=lesson_id)
        elif media_type == 'superbook':
            model_reference = LessonSuperbook(lesson_id=lesson_id)
        elif media_type == 'henkieshow':
            model_reference = LessonHenkieshow(lesson_id=lesson_id)
        elif media_type == 'shortmovie':
            model_reference = LessonShortMovie(lesson_id=lesson_id)
        elif media_type == 'drawing':
            model_reference = LessonDrawing(lesson_id=lesson_id)
        elif media_type == 'testimony':
            model_reference = LessonTestimony(lesson_id=lesson_id)
        elif media_type == 'picture':
            model_reference = LessonPicture(lesson_id=lesson_id)
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

    def _add_lesson(self, lesson):
        try:
            model_lesson, is_new = Lesson.objects.get_or_create(id=lesson.id)
            model_lesson.save()

            if is_new:
                print(f'Added lesson {model_lesson.id}')
            else:
                print(f'Updating lesson {model_lesson.id}')

            for item in lesson.media:
                self._add_media(model_lesson.id, item)
        except Exception as ex:
            print(ex)
            print(f'Failed to import {lesson.id}')

    def _save(self, model_object):
        try:
            model_object.save()
            print(f'Added {model_object}.')
        except IntegrityError:
            print(f'Skipped {model_object} as it already exists.')
        except Exception as ex:
            print(f'Failed inserting {model_object} with error {ex}.')
