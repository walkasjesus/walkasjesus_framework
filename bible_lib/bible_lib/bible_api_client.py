import logging

import requests

from config import API_KEY


class BibleApiClient:
    def __init__(self):
        self.server_url = 'https://api.scripture.api.bible/'
        self.api_version = 'v1'
        self.logger = logging.getLogger()

    @property
    def _base_url(self):
        return '{}/{}/'.format(self.server_url.rstrip('/'), self.api_version)

    def get(self, relative_path: str):
        url = self._base_url + relative_path.lstrip('/')
        self.logger.info('GET {}'.format(url))
        return requests.get(url, headers={'api-key': API_KEY})
