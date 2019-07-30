import pandas

from import_tool.bible_reference import BibleReference
from import_tool.commandment import Commandment


class CommandmentImporter(object):
    def load(self, file_path='../../../volto_website/data/commandments.csv'):
        df = pandas.read_csv(file_path, delimiter=';')

        commandments = []

        # Handle each commandment
        for name, group in df.groupby(['Step']):
            commandment = Commandment()
            if len(group['QuoteDutch'].dropna()) > 0:
                commandment.title = group['QuoteEnglish'].dropna().iloc[0]
                commandment.category = group['Category'].dropna().iloc[0]
            # A commandment has several bible refs.
            for index, row in group.iterrows():
                try:
                    reference = BibleReference.create_from_string(row['BiblePhrase'])
                    reference.is_primary = row['PrimarySecondary'].lower() == 'primary'
                    commandment.bible_references.append(reference)
                except Exception as ex:
                    print(f'Could not parse {row}')
            commandments.append(commandment)

        return commandments
