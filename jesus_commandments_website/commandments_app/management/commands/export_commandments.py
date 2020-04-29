from django.core.management import BaseCommand
from pandas import DataFrame

from commandments_app.models import *


class Command(BaseCommand):
    """ Export the commandments in the database to a csv file. """
    def __init__(self):
        super().__init__()
        columns = ['step',
                   'bible_ref',
                   'bible_ref_positive_negative',
                   'bible_ref_ot_nr',
                   'bible_ref_ot_rambam_id',
                   'bible_ref_ot_rambam_title',
                   'bible_ref_author',
                   'bible_ref_type',
                   'category',
                   'title_en',
                   'title_negative_en',
                   'questions',
                   'quote',
                   'quote_source']

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
        [self.export_bible_reference(item, 'otlaw') for item in obj.otlaw_bible_references()]
        [self.export_bible_reference(item, 'wisdom') for item in obj.wisdom_bible_references()]

    def export_main_content(self, obj):
        self.write_field('step', obj.id)
        self.write_field('category', CommandmentCategories[obj.category].value)
        self.write_field('title_en', obj.title)
        self.write_field('title_negative_en', obj.title_negative)
        self.write_field('quote', obj.quote)
        self.write_field('quote_source', obj.quote_source)
        self.start_new_row()

    def export_bible_reference(self, bible_ref: BibleReference, reference_type: str):
        self.write_field('step', bible_ref.commandment.id)
        self.write_field('bible_ref', bible_ref.short_name())
        self.write_field('bible_ref_positive_negative', bible_ref.positive_negative)
        self.write_field('bible_ref_ot_nr', bible_ref.ot_nr)
        self.write_field('bible_ref_ot_rambam_id', bible_ref.ot_rambam_id)
        self.write_field('bible_ref_ot_rambam_title', bible_ref.ot_rambam_title)
        self.write_field('bible_ref_author', bible_ref.author)
        self.write_field('bible_ref_type', reference_type)
        self.start_new_row()

    def export_questions(self, question):
        if question.text != '':
            self.write_field('step', question.commandment.id)
            self.write_field('questions', question.text)
            self.start_new_row()

    def write_field(self, column_name, value):
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
