import logging
import requests

from bible_lib.config import API_KEY
from bible_lib.exceptions import *


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

        try:
            response = requests.get(url, headers={'api-key': API_KEY})
        except Exception as ex:
            self.logger.error(f'GET request for {relative_path} failed.')
            self.logger.error(ex)
            raise ex

        if response.ok:
            return response.text
        if response.status_code == '400':
            self.logger.warning('Invalid ID supplied.')
            raise BadRequestException()
        if response.status_code == '401':
            self.logger.warning('The API key provided is either missing, invalid, or unauthorized for API access.')
            raise UnauthorizedException()
        if response.status_code == '403':
            self.logger.warning('Server understood the request, but provided API key is not authorized to retrieve '
                                'this information.')
            raise UnauthorizedException()
        if response.status_code == '404':
            self.logger.warning('Resource not found.')
            raise NotFoundException()

        raise Exception(f'GET {relative_path} failed with status code {response.status_code}.')
