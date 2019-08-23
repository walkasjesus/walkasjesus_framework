import json
import logging

from bible_lib.api_bible import ApiBible
from bible_lib.hsv_bible import HsvBible
from bible_lib.services import Services


class Bibles(object):
    def __init__(self):
        self.client = Services().api_client
        self.logger = logging.getLogger()

    def dictionary(self) -> {}:
        """ Return a dictionary with key:Bible """
        try:
            response = self.client.get('bibles')
        except Exception as ex:
            self.logger.warning('Failed to retrieve bible list data.')
            self.logger.warning(ex)
            return {}

        try:
            bible_entries = json.loads(response)['data']
        except Exception as ex:
            self.logger.warning('Failed to parse bible list.')
            self.logger.warning(ex)
            return {}

        try:
            bibles = {}

            # Hard coded add HSV
            bibles['hsv'] = HsvBible()

            for bible_entry in bible_entries:
                bible = ApiBible()
                bible.id = bible_entry['id']
                bible.name = bible_entry['nameLocal']
                bible.language = self.get_language_code(bible_entry)
                bibles[bible.id] = bible
        except Exception as ex:
            self.logger.warning('Failed to parse at least on of the bible entries.')
            self.logger.warning(ex)
            return {}

        return bibles

    def list(self) -> []:
        """ Return a list of Bible. """
        return list(self.dictionary().values())

    def get_language_code(self, bible_entry):
        mapping = {'nederlands': 'nl',
                   'english': 'en',
                   'deutsch': 'de',
                   'français': 'fr',
                   }

        api_language_name = bible_entry['language']['nameLocal'].lower()

        if api_language_name in mapping:
            return mapping[api_language_name]
        else:
            return api_language_name
