import pandas

from import_tool.bible_reference import BibleReference
from import_tool.lesson import Lesson
from import_tool.lesson_media import LessonMedia


def first(data_frame, column):
    cleaned_column = data_frame[column].dropna()

    if not cleaned_column.any():
        return ''

    return cleaned_column.iloc[0]


class LessonMediaImporter(object):
    def load(self, file_path='../../../jesus_commandments_website/data/media/media_lessons.csv'):
        df = pandas.read_csv(file_path, delimiter=';', na_filter= False)

        lessons = []

        # Handle each lesson
        for name, group in df.groupby(['lesson']):
            lesson = Lesson()
            lesson.id = first(group, 'lesson')

            # Parse media
            for index, row in group.iterrows():
                if isinstance(row['media_type'], str):
                    media = LessonMedia()
                    media.title = row['media_title']
                    media.description = row['media_description_en']
                    media.target_audience = row['media_target_audience']
                    media.language = row['media_lang']
                    media.img_url = row['media_img_url']
                    media.url = row['media_url']
                    media.type = row['media_type']
                    media.author = row['media_author']
                    media.is_public = str(row['media_public']).lower() == 'yes'
                    lesson.media.append(media)

            lessons.append(lesson)

        return lessons
