import json
import logging

import pycountry

from bible_lib.bible_api.api_bible import ApiBible
from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_hsv.hsv_bible import HsvBible
from bible_lib.performance_time_decorator import performance_time


class Bibles(object):
    def __init__(self):
        self.client = CachedBibleApiClient()
        self.logger = logging.getLogger()
        self.query_builder = QueryBuilder()

    def dictionary(self) -> {}:
        """ Return a dictionary with key:Bible """
        try:
            response = self.client.get(self.query_builder.get_bibles())
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
            bibles = {'hsv': HsvBible()}

            for bible_entry in bible_entries:
                bible = ApiBible()
                bible.id = bible_entry['id']
                bible.name = self.create_unique_name(bible_entry, bible_entries)
                bible.language = self._get_language_code(bible_entry)
                bibles[bible.id] = bible

        except Exception as ex:
            self.logger.warning('Failed to parse at least one of the bible entries.')
            self.logger.warning(ex)
            return {}

        return bibles

    def create_unique_name(self, bible_entry, bible_entries):
        name = bible_entry['nameLocal']
        description = bible_entry['descriptionLocal']

        bible_names = [b['nameLocal'] for b in bible_entries]
        bible_names_descriptions = [(b['nameLocal'], b['descriptionLocal']) for b in bible_entries]

        if bible_names.count(name) > 1:
            if name == 'Translation for Translators':
                bible_id = bible_entry['id']
                return f'{name} ({bible_id})'
            if bible_names_descriptions.count((name, description)) > 1:
                abbreviation = bible_entry['abbreviationLocal']
                return f'{name} ({abbreviation})'

            translation_variant = bible_entry['descriptionLocal']
            return f'{name} ({translation_variant})'

        return name

    def list(self) -> []:
        """ Return a list of Bible. """
        return list(self.dictionary().values())

    def _get_language_code(self, bible_entry):
        api_code = bible_entry['language']['id']
        language_code = pycountry.languages.get(alpha_3=api_code)

        if hasattr(language_code, 'alpha_2'):
            return language_code.alpha_2

        return api_code
