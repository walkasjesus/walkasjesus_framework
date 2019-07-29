import pandas

from import_tool.bible_reference import BibleReference
from import_tool.calling import Calling


class CallingImporter(object):
    def load(self, file_path='../../../volto_website/data/callings.csv'):
        df = pandas.read_csv(file_path, delimiter=';')

        callings = []

        # Handle each commandment
        for name, group in df.groupby(['Step']):
            calling = Calling()
            if len(group['QuoteDutch'].dropna()) > 0:
                calling.quote = group['QuoteDutch'].dropna().iloc[0]
            # A commandment has several bible refs.
            for verse in df['BiblePhrase'].dropna():
                try:
                    calling.bible_references.append(BibleReference.create_from_string(verse))
                except Exception as ex:
                    print(f'Could not parse {verse} from {name}')
            callings.append(calling)

        return callings
