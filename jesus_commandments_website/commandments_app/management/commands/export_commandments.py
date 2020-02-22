from django.core.management import BaseCommand
from pandas import DataFrame

from commandments_app.models import *


class Command(BaseCommand):
    """ Export the commandments in the database to a csv file. """
    def __init__(self):
        columns = ['step',
                   'category',
                   'bible_trans_nl_trans_text',
                   'Principles',
                   'title_nl',
                   'title_en',
                   'title_ot_nl',
                   'title_ot_en',
                   'title_negative_en',
                   'quote',
                   'quote_source',
                   'extra',
                   'bible_ref',
                   'bible_ref_positive_negative',
                   'bible_ref_literal_figurative',
                   'bible_ref_origin',
                   'bible_ref_author',
                   'bible_ref_type',
                   ]

        self.data_frame = DataFrame(columns=columns)
        self.last_row_index = 0

    def handle(self, *args, **options):
        commandments = Commandment.objects.all()

        for item in commandments:
            self.export_commandment(item)

    def export_commandment(self, obj: Commandment):
        # language, what is default when running command?
        # and how to get both nl and en for export?

        self.data_frame.at[self.last_row_index, 'step'] = obj.id
        self.data_frame.at[self.last_row_index, 'category'] = ''
        self.data_frame.at[self.last_row_index, 'bible_trans_nl_trans_text'] = ''
        self.data_frame.at[self.last_row_index, 'Principles'] = ''
        self.data_frame.at[self.last_row_index, 'title_nl'] = ''
        self.data_frame.at[self.last_row_index, 'title_en'] = ''
        self.data_frame.at[self.last_row_index, 'title_ot_nl'] = ''
        self.data_frame.at[self.last_row_index, 'title_ot_en'] = ''
        self.data_frame.at[self.last_row_index, 'title_negative_en'] = ''
        self.data_frame.at[self.last_row_index, 'quote'] = obj.quote
        self.data_frame.at[self.last_row_index, 'quote_source'] = obj.quote_source
        # self.data_frame.at[self.last_row_index, 'extra'] = ''

        self.last_row_index += 1

        self.export_bible_reference(obj.primary_bible_reference(), 'primary')
        [self.export_bible_reference(item, 'direct') for item in obj.direct_bible_references()]
        [self.export_bible_reference(item, 'indirect') for item in obj.indirect_bible_references()]
        [self.export_bible_reference(item, 'duplicate') for item in obj.duplicate_bible_references()]
        [self.export_bible_reference(item, 'example') for item in obj.example_bible_references()]
        [self.export_bible_reference(item, 'study') for item in obj.study_bible_references()]


    def export_bible_reference(self, bible_ref, type) -> [str]:
        self.data_frame.at[self.last_row_index, 'bible_ref'] = str(bible_ref)
        self.data_frame.at[self.last_row_index, 'bible_ref_positive_negative'] = bible_ref.positive_negative
        # self.data_frame.at[self.last_row_index, 'bible_ref_literal_figurative'] = bible_ref.
        self.data_frame.at[self.last_row_index, 'bible_ref_origin'] = bible_ref.origin
        self.data_frame.at[self.last_row_index, 'bible_ref_author'] = bible_ref.author
        self.data_frame.at[self.last_row_index, 'bible_ref_type'] = type

        self.last_row_index += 1
