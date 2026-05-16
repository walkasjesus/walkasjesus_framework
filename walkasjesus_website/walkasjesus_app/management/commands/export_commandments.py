import csv

from django.core.management import BaseCommand
from pandas import DataFrame

from walkasjesus_app.models import *


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
        commandments = Commandment.objects.order_by('id')
        self.line_terminator = self._detect_lineterminator(destination_csv)
        existing_order = self._existing_row_order(destination_csv)
        self.existing_main_rows = self._existing_main_rows(destination_csv)

        for item in commandments:
            self.export_commandment(item)

        records = []
        for index, (_, row) in enumerate(self.data_frame.fillna('').iterrows()):
            record = {column: row.get(column, '') for column in self.data_frame.columns}
            identity = self._row_identity_from_dict(record)
            records.append((identity, index, record))

        records.sort(key=lambda item: self._sort_key(item[0], item[1], existing_order))

        sorted_records = [record for _, _, record in records]
        self.data_frame = DataFrame(sorted_records, columns=self.data_frame.columns)

        self.data_frame.to_csv(
            destination_csv,
            index=False,
            sep=';',
            lineterminator=self.line_terminator,
        )

        print(f'Written export to {destination_csv}')

    def _existing_row_order(self, destination_csv):
        order = {}
        try:
            with open(destination_csv, 'r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle, delimiter=';')
                for index, row in enumerate(reader):
                    identity = self._row_identity_from_dict(row)
                    if identity not in order:
                        order[identity] = index
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return order

    def _existing_main_rows(self, destination_csv):
        rows = {}
        try:
            with open(destination_csv, 'r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle, delimiter=';')
                for row in reader:
                    identity = self._row_identity_from_dict(row)
                    if identity[0] != 'main':
                        continue
                    step = str((row or {}).get('step', '') or '').strip()
                    if step and step not in rows:
                        rows[step] = row
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return rows

    def _row_identity_from_dict(self, row):
        step = str((row or {}).get('step', '') or '').strip()
        bible_ref = str((row or {}).get('bible_ref', '') or '').strip()
        bible_type = str((row or {}).get('bible_ref_type', '') or '').strip()
        question = str((row or {}).get('questions', '') or '').strip()

        if bible_ref or bible_type:
            return (
                'reference',
                step,
                bible_type,
                bible_ref,
            )

        if question:
            return (
                'question',
                step,
                question,
            )

        return (
            'main',
            step,
        )

    def _sort_key(self, identity, export_index, existing_order):
        if identity in existing_order:
            return (0, existing_order[identity], export_index)
        return (1, export_index)

    def _detect_lineterminator(self, destination_csv):
        try:
            with open(destination_csv, 'rb') as handle:
                sample = handle.read(4096)
            if b'\r\n' in sample:
                return '\r\n'
        except FileNotFoundError:
            pass
        return '\n'

    def _is_legacy_category(self, category_value):
        if not category_value:
            return False
        if category_value in CommandmentCategories.__members__:
            return True
        try:
            CommandmentCategories(category_value)
            return True
        except ValueError:
            return False

    def _existing_category_for_step(self, step):
        row = self.existing_main_rows.get(str(step), {})
        return str((row or {}).get('category', '') or '').strip()

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
        category_value = obj.category
        try:
            # Preferred: model stores enum key (e.g. "firstcommandment").
            category_value = CommandmentCategories[obj.category].value
        except KeyError:
            try:
                # Compatibility: model stores enum label (e.g. "First Commandment").
                category_value = CommandmentCategories(obj.category).value
            except ValueError:
                # Keep unknown/new category values as-is instead of crashing export.
                category_value = obj.category

        existing_category = self._existing_category_for_step(obj.id)
        if existing_category and self._is_legacy_category(category_value) and not self._is_legacy_category(existing_category):
            category_value = existing_category

        self.write_field('step', obj.id)
        self.write_field('category', category_value)
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
        if isinstance(value, str):
            value = value.replace('\r\n', '\n').replace('\r', '\n')
            if self.line_terminator == '\r\n':
                value = value.replace('\n', '\r\n')
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
