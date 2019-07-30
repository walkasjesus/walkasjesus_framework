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
            # A commandment has several bible refs.
            for verse in group['BiblePhrase'].dropna():
                try:
                    commandment.bible_references.append(BibleReference.create_from_string(verse))
                except Exception as ex:
                    print(f'Could not parse {verse} from {name}')
            commandments.append(commandment)

        return commandments
