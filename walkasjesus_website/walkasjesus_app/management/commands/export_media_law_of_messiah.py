from django.core.management import BaseCommand
from pandas import DataFrame

from walkasjesus_app.models import LawOfMessiahDrawing


class Command(BaseCommand):
    """Export Law of Messiah media in the database to a csv file."""

    def __init__(self):
        super().__init__()
        columns = [
            'lawofmessiah',
            'step',
            'lesson',
            'media_author',
            'media_title',
            'media_description_en',
            'media_target_audience',
            'media_lang',
            'media_type',
            'media_public',
            'media_img_url',
            'media_url',
        ]

        self.data_frame = DataFrame(columns=columns)
        self.last_row_index = 0

    def add_arguments(self, parser):
        parser.add_argument('destination', type=str, help='The file name and path to write the export to.')

    def handle(self, *args, **options):
        destination_csv = options['destination']
        self.line_terminator = self._detect_lineterminator(destination_csv)
        rows = LawOfMessiahDrawing.objects.select_related('law_of_messiah', 'commandment', 'lesson').order_by('law_of_messiah_id', 'commandment_id', 'lesson_id', 'media_type', 'id')

        for media in rows:
            self.write_field('lawofmessiah', media.law_of_messiah.id if media.law_of_messiah else '')
            self.write_field('step', media.commandment.id if media.commandment else '')
            self.write_field('lesson', media.lesson.id if media.lesson else '')
            self.write_field('media_author', media.author)
            self.write_field('media_title', media.title)
            self.write_field('media_description_en', media.description)
            self.write_field('media_target_audience', media.target_audience)
            self.write_field('media_lang', media.language)
            self.write_field('media_type', media.media_type)
            self.write_field('media_public', 'yes' if media.is_public else 'no')
            self.write_field('media_img_url', media.img_url)
            self.write_field('media_url', media.url)
            self.start_new_row()

        self.data_frame.to_csv(
            destination_csv,
            index=False,
            sep=';',
            lineterminator=self.line_terminator,
        )
        self.stdout.write(f'Written export to {destination_csv}')

    def _detect_lineterminator(self, destination_csv):
        try:
            with open(destination_csv, 'rb') as handle:
                sample = handle.read(4096)
            if b'\r\n' in sample:
                return '\r\n'
        except FileNotFoundError:
            pass
        return '\n'

    def write_field(self, column_name, value):
        if isinstance(value, str):
            value = value.replace('\r\n', '\n').replace('\r', '\n')
            if self.line_terminator == '\r\n':
                value = value.replace('\n', '\r\n')
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
