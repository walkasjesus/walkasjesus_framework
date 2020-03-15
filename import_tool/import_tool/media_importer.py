import pandas

from import_tool.bible_reference import BibleReference
from import_tool.commandment import Commandment
from import_tool.media import Media


def first(data_frame, column):
    cleaned_column = data_frame[column].dropna()

    if not cleaned_column.any():
        return ''

    return cleaned_column.iloc[0]


class MediaImporter(object):
    def load(self, file_path='../../../jesus_commandments_website/data/media/media.csv'):
        df = pandas.read_csv(file_path, delimiter=';', na_filter= False)

        commandments = []

        # Handle each commandment
        for name, group in df.groupby(['step']):
            commandment = Commandment()
            commandment.id = first(group, 'step')

            # Parse media
            for index, row in group.iterrows():
                if isinstance(row['media_type'], str):
                    media = Media()
                    media.title = row['media_title']
                    media.description = row['media_description_en']
                    media.target_audience = row['media_target_audience']
                    media.language = row['media_lang']
                    media.img_url = row['media_img_url']
                    media.url = row['media_url']
                    media.type = row['media_type']
                    media.author = row['media_author']
                    media.is_public = str(row['media_public']).lower() == 'yes'
                    commandment.media.append(media)

            commandments.append(commandment)

        return commandments
