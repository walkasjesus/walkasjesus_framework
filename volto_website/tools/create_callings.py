import pandas

callings_data_frame = pandas.read_csv('./data/callings.csv', delimiter=';')

quotes = callings_data_frame['Bijbeloproep (synopsis)'].dropna().to_list()

from callings_app.models import Calling

print('Adding %s quotes' % len(quotes))


def add(quote):
    calling = Calling()
    calling.quote = quote
    calling.save()


[add(quote) for quote in quotes]
