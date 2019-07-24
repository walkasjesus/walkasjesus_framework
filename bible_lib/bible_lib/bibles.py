import json

from bible import Bible
from bible_api_client import BibleApiClient


class Bibles(object):
    def __init__(self):
        self.client = BibleApiClient()

    def list(self):
        response_string = self.client.get('bibles')
        bible_entries = json.loads(response_string)['data']

        bibles = []

        for bible_entry in bible_entries:
            bible = Bible()
            bible.id = bible_entry['id']
            bible.name = bible_entry['nameLocal']
            bible.language = bible_entry['language']['nameLocal']
            bibles.append(bible)

        return bibles
