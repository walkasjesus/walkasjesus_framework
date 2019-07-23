from bible_api_client import BibleApiClient


class Bibles(object):
    def __init__(self):
        self.client = BibleApiClient()

    def list(self):
        response = self.client.get('bibles')

        print(response.text)
        print()
