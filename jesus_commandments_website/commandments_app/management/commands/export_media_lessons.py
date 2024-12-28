from django.core.management import BaseCommand
from pandas import DataFrame

from commandments_app.models import Lesson, LessonMedia


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

        for lesson in lessons:
            [self.export_media(item, 'song') for item in lesson.lessonsong_set.all()]
            [self.export_media(item, 'superbook') for item in lesson.lessonsuperbook_set.all()]
            [self.export_media(item, 'henkieshow') for item in lesson.lessonhenkieshow_set.all()]
            [self.export_media(item, 'shortmovie') for item in lesson.lessonshortmovie_set.all()]
            [self.export_media(item, 'drawing') for item in lesson.lessondrawing_set.all()]
            [self.export_media(item, 'testimony') for item in lesson.lessontestimony_set.all()]
            [self.export_media(item, 'picture') for item in lesson.lessonpicture_set.all()]

        self.data_frame.to_csv(options['destination'], index=False, sep=';')
        print(f'Written export to {destination_csv}')

    def export_media(self, media: LessonMedia, media_type: str):
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
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
