import pandas


class CallingImporter(object):
    def load(self, file_path='../../../volto_website/data/callings.csv'):
        df = pandas.read_csv(file_path, delimiter=';')
        #df = callings_data_frame['Bijbeloproep (synopsis)'].dropna().to_list()
        callings = df.groupby(['Stap'])

        for name, group in callings:
            bible_references_as_string = df['Bijbeltekst']
            print('watnu')

