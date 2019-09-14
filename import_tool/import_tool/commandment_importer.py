import pandas

from import_tool.bible_reference import BibleReference
from import_tool.commandment import Commandment
from import_tool.media import Media


def first(data_frame, column):
    cleaned_column = data_frame[column].dropna()

    if not cleaned_column.any():
        return ''

    return cleaned_column.iloc[0]


class CommandmentImporter(object):
    def load(self, file_path='../../../jesus_commandments_website/data/commandments.csv'):
        df = pandas.read_csv(file_path, delimiter=';')

        commandments = []

        # Handle each commandment
        for name, group in df.groupby(['step']):
            commandment = Commandment()
            commandment.id = first(group, 'step')
            commandment.title = first(group, 'title_en')
            commandment.title_negative = first(group, 'title_negative_en')
            commandment.title_nl = first(group, 'title_nl')
            commandment.devotional = first(group, 'devotional_en')
            commandment.devotional_nl = first(group, 'devotional_nl')
            commandment.devotional_source = first(group, 'devotional_source')
            commandment.category = first(group, 'category')
            commandment.quote = first(group, 'quote')
            commandment.quote_source = first(group, 'quote_source')

            # Parse bible refs
            for index, row in group.iterrows():
                try:
                    reference = BibleReference.create_from_string(row['bible_ref'])
                    if row['precedence'].lower() == 'primary':
                        commandment.primary_bible_references.append(reference)
                    if row['precedence'].lower() == 'secondary':
                        commandment.secondary_bible_references.append(reference)
                    if row['precedence'].lower() == 'tertiary':
                        commandment.tertiary_bible_references.append(reference)
                except Exception as ex:
                    print(f'Could not parse {row}')

            # Parse media
            for index, row in group.iterrows():
                if isinstance(row['media_link'], str):
                    media = Media()
                    media.title = row['media_title']
                    media.description = row['media_description_en']
                    media.language = row['media_lang']
                    media.link = row['media_link']
                    media.type = row['media_type']
                    media.author = row['media_author']
                    media.is_public = str(row['media_public']).lower() == 'yes'
                    commandment.media.append(media)

            # Parse questions
            commandment.questions += group['questions'].dropna().tolist()

            commandments.append(commandment)

        return commandments
