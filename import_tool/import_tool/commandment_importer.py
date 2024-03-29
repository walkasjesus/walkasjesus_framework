import pandas

from import_tool.bible_reference import BibleReference
from import_tool.commandment import Commandment


def first(data_frame, column):
    cleaned_column = data_frame[column].dropna()

    if not cleaned_column.any():
        return ''

    return cleaned_column.iloc[0]


class CommandmentImporter(object):
    def load(self, file_path='../../../jesus_commandments_website/data/biblereferences/commandments.csv'):
        df = pandas.read_csv(file_path, delimiter=';', na_filter= False)

        commandments = []

        # Handle each commandment
        for name, group in df.groupby(['step']):
            commandment = Commandment()
            commandment.id = first(group, 'step')
            commandment.title = first(group, 'title_en')
            commandment.title_negative = first(group, 'title_negative_en')
            commandment.category = first(group, 'category')
            commandment.quote = first(group, 'quote')
            commandment.quote_source = first(group, 'quote_source')

            # Parse bible refs
            for index, row in group.iterrows():
                if len(row['bible_ref']) == 0:
                    continue
                try:
                    reference = BibleReference.create_from_string(row['bible_ref'])
                    reference.ot_nr = row['bible_ref_ot_nr']
                    reference.ot_rambam_id = row['bible_ref_ot_rambam_id']
                    reference.ot_rambam_title = row['bible_ref_ot_rambam_title']
                    reference.author = row['bible_ref_author']
                    reference.positive_negative = row['bible_ref_positive_negative']

                    if row['bible_ref_type'].lower() == 'primary':
                        commandment.primary_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'direct':
                        commandment.direct_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'indirect':
                        commandment.indirect_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'duplicate':
                        commandment.duplicate_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'example':
                        commandment.example_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'study':
                        commandment.study_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'otlaw':
                        commandment.otlaw_bible_references.append(reference)
                    if row['bible_ref_type'].lower() == 'wisdom':
                        commandment.wisdom_bible_references.append(reference)
                except Exception as ex:
                    print(f'Could not parse {row} due to exception {ex}')

            # Parse questions
            commandment.questions += [q for q in group['questions'] if q != '']

            commandments.append(commandment)

        return commandments
