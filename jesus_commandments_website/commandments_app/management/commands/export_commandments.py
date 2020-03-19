from django.core.management import BaseCommand
from pandas import DataFrame

from commandments_app.models import *


class Command(BaseCommand):
    """ Export the commandments in the database to a csv file. """

    def __init__(self):
        columns = ['step',
                   'bible_ref',
                   'bible_ref_positive_negative',
                   'bible_ref_origin',
                   'bible_ref_author',
                   'bible_ref_type',
                   'category',
                   'title_nl',
                   'title_ot_nl',
                   'title_ot_en',
                   'title_ot_code',
                   'title_en',
                   'title_negative_en',
                   'questions',
                   'quote',
                   'quote_source',
                   ]

        self.data_frame = DataFrame(columns=columns)
        self.last_row_index = 0

    def add_arguments(self, parser):
        parser.add_argument('destination', type=str, help='The file name and path to write the export to.')

    def handle(self, *args, **options):
        destination_csv = options['destination']
        commandments = Commandment.objects.all()

        for item in commandments:
            self.export_commandment(item)

        self.data_frame.to_csv(options['destination'], index=False, sep=';')

        print(f'Written export to {destination_csv}')

    def export_commandment(self, obj: Commandment):
        self.export_main_content(obj)

        self.export_bible_reference(obj.primary_bible_reference(), 'primary')
        [self.export_questions(item) for item in obj.questions()]
        [self.export_bible_reference(item, 'direct') for item in obj.direct_bible_references()]
        [self.export_bible_reference(item, 'indirect') for item in obj.indirect_bible_references()]
        [self.export_bible_reference(item, 'duplicate') for item in obj.duplicate_bible_references()]
        [self.export_bible_reference(item, 'example') for item in obj.example_bible_references()]
        [self.export_bible_reference(item, 'study') for item in obj.study_bible_references()]

    def export_main_content(self, obj):
        self.data_frame.at[self.last_row_index, 'step'] = obj.id
        self.data_frame.at[self.last_row_index, 'category'] = CommandmentCategories[obj.category].value
        self.data_frame.at[self.last_row_index, 'title_en'] = obj.title
        self.data_frame.at[self.last_row_index, 'title_negative_en'] = obj.title_negative
        self.data_frame.at[self.last_row_index, 'quote'] = obj.quote
        self.data_frame.at[self.last_row_index, 'quote_source'] = obj.quote_source
        self.last_row_index += 1

    def export_bible_reference(self, bible_ref, reference_type):
        self.data_frame.at[self.last_row_index, 'step'] = bible_ref.commandment.id
        self.data_frame.at[self.last_row_index, 'bible_ref'] = str(bible_ref)
        self.data_frame.at[self.last_row_index, 'bible_ref_positive_negative'] = bible_ref.positive_negative
        self.data_frame.at[self.last_row_index, 'bible_ref_origin'] = bible_ref.origin
        self.data_frame.at[self.last_row_index, 'bible_ref_author'] = bible_ref.author
        self.data_frame.at[self.last_row_index, 'bible_ref_type'] = reference_type
        self.last_row_index += 1

    def export_questions(self, question):
        self.data_frame.at[self.last_row_index, 'step'] = question.commandment.id
        self.data_frame.at[self.last_row_index, 'questions'] = question
        self.last_row_index += 1
