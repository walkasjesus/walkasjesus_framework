import os

from django.core.management import BaseCommand
from django.db import IntegrityError
from import_tool import CommandmentImporter

from commandments_app.models import *
from jesus_commandments_website.settings import BASE_DIR


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='The file name and path to read the data from.')

    def handle(self, *args, **options):
        if 'source' in options:
            file_path = options['source']
        else:
            file_path = os.path.join(BASE_DIR, 'data', 'biblereferences', 'commandments.csv')

        importer = CommandmentImporter()
        commandments = importer.load(file_path)

        print(f'Adding {len(commandments)} commandments from {file_path}')
        for item in commandments:
            self._add_commandment(item)

    def _add_bible_ref(self, model_reference, reference):
        model_reference.book = reference.book.name
        model_reference.begin_chapter = reference.start_chapter
        model_reference.begin_verse = reference.start_verse
        model_reference.end_chapter = reference.end_chapter
        model_reference.end_verse = reference.end_verse
        model_reference.positive_negative = reference.positive_negative
        model_reference.ot_nr = reference.ot_nr
        model_reference.ot_rambam_id = reference.ot_rambam_id
        model_reference.ot_rambam_title = reference.ot_rambam_title
        model_reference.author = reference.author

        self._save(model_reference)

    def _add_question(self, commandment_id, question):
        question_model = Question(commandment_id=commandment_id)
        question_model.text = question
        self._save(question_model)

    def _add_commandment(self, commandment):
        try:
            model_commandment, is_new = Commandment.objects.get_or_create(id=commandment.id)
            model_commandment.title = commandment.title
            model_commandment.title_negative = commandment.title_negative
            model_commandment.category = CommandmentCategories(commandment.category).name
            model_commandment.quote = commandment.quote
            model_commandment.quote_source = commandment.quote_source
            model_commandment.save()

            if is_new:
                print(f'Added commandment {model_commandment.id}')
            else:
                print(f'Updating commandment {model_commandment.id}')

            for item in commandment.primary_bible_references:
                self._add_bible_ref(PrimaryBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.direct_bible_references:
                self._add_bible_ref(DirectBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.indirect_bible_references:
                self._add_bible_ref(IndirectBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.duplicate_bible_references:
                self._add_bible_ref(DuplicateBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.example_bible_references:
                self._add_bible_ref(ExampleBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.study_bible_references:
                self._add_bible_ref(StudyBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.otlaw_bible_references:
                self._add_bible_ref(OTLawBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.wisdom_bible_references:
                self._add_bible_ref(WisdomBibleReference(commandment_id=model_commandment.id), item)
            for item in commandment.questions:
                self._add_question(model_commandment.id, item)
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
