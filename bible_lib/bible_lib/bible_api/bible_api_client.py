import logging
import requests

from bible_lib.exceptions import *


class BibleApiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.logger = logging.getLogger()

    def get(self, url: str):
        self.logger.info('GET {}'.format(url))

        try:
            response = requests.get(url, headers={'api-key': self.api_key})
        except Exception as ex:
            self.logger.error(f'GET request for {url} failed.')
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

        raise Exception(f'GET {url} failed with status code {response.status_code}.')
