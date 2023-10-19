import os

from django.core.management import BaseCommand
from django.db import IntegrityError
from import_tool import LessonImporter

from commandments_app.models import Lesson, LessonCategories, PrimaryLessonBibleReference, LessonBibleSection, LessonQuestion
from jesus_commandments_website.settings import BASE_DIR


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='The file name and path to read the data from.')

    def handle(self, *args, **options):
        if 'source' in options:
            file_path = options['source']
        else:
            file_path = os.path.join(BASE_DIR, 'data', 'biblereferences', 'lessons.csv')

        importer = LessonImporter()
        lessons = importer.load(file_path)

        print(f'Adding {len(lessons)} lessons from {file_path}')
        for item in lessons:
            self._add_lesson(item)

    def _add_bible_ref(self, model_reference, reference):
        model_reference.book = reference.book.name
        model_reference.begin_chapter = reference.start_chapter
        model_reference.begin_verse = reference.start_verse
        model_reference.end_chapter = reference.end_chapter
        model_reference.end_verse = reference.end_verse

        self._save(model_reference)

    def _add_question(self, lesson_id, question):
        question_model = LessonQuestion(lesson_id=lesson_id)
        question_model.text = question
        self._save(question_model)

    def _add_lesson(self, lesson):
        try:
            model_lesson, is_new = Lesson.objects.get_or_create(id=lesson.id)
            model_lesson.title = lesson.title
            model_lesson.category = LessonCategories[lesson.category].name
            model_lesson.commandment = lesson.commandment
            model_lesson.save()

            if is_new:
                print(f'Added lesson {model_lesson.id}')
            else:
                print(f'Updating lesson {model_lesson.id}')

            # Save the Lesson object
            model_lesson.save()

            for item in lesson.primary_lesson_bible_references:
                self._add_bible_ref(PrimaryLessonBibleReference(lesson_id=model_lesson.id), item)
            for item in lesson.lesson_bible_section:
                self._add_bible_ref(LessonBibleSection(lesson_id=model_lesson.id), item)
            for item in lesson.lessonquestions:
                self._add_question(model_lesson.id, item)
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
            print(f'Skipped {str(model_object)} as it already exists.')
        except Exception as ex:
            print(f'Failed inserting {model_object} with error {ex}.')
