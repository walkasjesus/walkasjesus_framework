from django.core.management import BaseCommand
from pandas import DataFrame

from walkasjesus_app.models import Lesson, LessonMedia
from walkasjesus_app.media_resource_matcher import has_shared_lesson_media


class Command(BaseCommand):
    """ Export the media lessons in the database to a csv file. """
    def __init__(self):
        super().__init__()
        columns = ['lesson',
                   'media_author',
                   'media_title',
                   'media_description_en',
                   'media_target_audience',
                   'media_lang',
                   'media_type',
                   'media_public',
                   'media_img_url',
                   'media_url'
                   ]

        self.data_frame = DataFrame(columns=columns)
        self.last_row_index = 0

    def add_arguments(self, parser):
        parser.add_argument('destination', type=str, help='The file name and path to write the export to.')

    def handle(self, *args, **options):
        destination_csv = options['destination']
        lessons = Lesson.objects.all()
        self.line_terminator = self._detect_lineterminator(destination_csv)

        for lesson in lessons:
            [self.export_media(item, 'song') for item in lesson.lessonsong_set.all()]
            [self.export_media(item, 'superbook') for item in lesson.lessonsuperbook_set.all()]
            [self.export_media(item, 'henkieshow') for item in lesson.lessonhenkieshow_set.all()]
            [self.export_media(item, 'shortmovie') for item in lesson.lessonshortmovie_set.all()]
            [self.export_media(item, 'drawing') for item in lesson.lessondrawing_set.all()]
            [self.export_media(item, 'testimony') for item in lesson.lessontestimony_set.all()]
            [self.export_media(item, 'picture') for item in lesson.lessonpicture_set.all()]

        self.data_frame.to_csv(
            destination_csv,
            index=False,
            sep=';',
            lineterminator=self.line_terminator,
        )
        print(f'Written export to {destination_csv}')

    def _detect_lineterminator(self, destination_csv):
        try:
            with open(destination_csv, 'rb') as handle:
                sample = handle.read(4096)
            if b'\r\n' in sample:
                return '\r\n'
        except FileNotFoundError:
            pass
        return '\n'

    def export_media(self, media: LessonMedia, media_type: str):
        if has_shared_lesson_media(
            media.lesson_id,
            media_type=media_type,
            title=media.title,
            description=media.description,
            target_audience=media.target_audience,
            language=media.language,
            img_url=media.img_url,
            url=media.url,
            author=media.author,
            is_public=media.is_public,
        ):
            return

        self.write_field('lesson', media.lesson.id)
        self.write_field('media_author', media.author)
        self.write_field('media_title', media.title)
        self.write_field('media_description_en', media.description)
        self.write_field('media_target_audience', media.target_audience)
        self.write_field('media_lang', media.language)
        self.write_field('media_type', media_type)
        self.write_field('media_public', 'yes' if media.is_public else 'no')
        self.write_field('media_img_url', media.img_url)
        self.write_field('media_url', media.url)
        self.start_new_row()

    def write_field(self, column_name, value):
        if isinstance(value, str):
            value = value.replace('\r\n', '\n').replace('\r', '\n')
            if self.line_terminator == '\r\n':
                value = value.replace('\n', '\r\n')
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
