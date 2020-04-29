from django.core.management import BaseCommand
from pandas import DataFrame

from commandments_app.models import *


class Command(BaseCommand):
    """ Export the media in the database to a csv file. """
    def __init__(self):
        super().__init__()
        columns = ['step',
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
        commandments = Commandment.objects.all()

        for commandment in commandments:
            [self.export_media(item, 'song') for item in commandment.song_set.all()]
            [self.export_media(item, 'superbook') for item in commandment.superbook_set.all()]
            [self.export_media(item, 'movie') for item in commandment.movie_set.all()]
            [self.export_media(item, 'shortmovie') for item in commandment.shortmovie_set.all()]
            [self.export_media(item, 'drawing') for item in commandment.drawing_set.all()]
            [self.export_media(item, 'testimony') for item in commandment.testimony_set.all()]
            [self.export_media(item, 'blog') for item in commandment.blog_set.all()]
            [self.export_media(item, 'picture') for item in commandment.picture_set.all()]
            [self.export_media(item, 'sermon') for item in commandment.sermon_set.all()]
            [self.export_media(item, 'book') for item in commandment.book_set.all()]

        self.data_frame.to_csv(options['destination'], index=False, sep=';')
        print(f'Written export to {destination_csv}')

    def export_media(self, media: Media, media_type: str):
        self.data_frame.at[self.last_row_index, 'step'] = media.commandment.id
        self.data_frame.at[self.last_row_index, 'media_author'] = media.author
        self.data_frame.at[self.last_row_index, 'media_title'] = media.title
        self.data_frame.at[self.last_row_index, 'media_description_en'] = media.description
        self.data_frame.at[self.last_row_index, 'media_target_audience'] = media.target_audience
        self.data_frame.at[self.last_row_index, 'media_lang'] = media.language
        self.data_frame.at[self.last_row_index, 'media_type'] = media_type
        self.data_frame.at[self.last_row_index, 'media_public'] = 'yes' if media.is_public else 'no'
        self.data_frame.at[self.last_row_index, 'media_img_url'] = media.img_url
        self.data_frame.at[self.last_row_index, 'media_url'] = media.url
        self.last_row_index += 1
