import logging

from bible_api_client import BibleApiClient
from file_cache import SimpleCache


class FileCachedBibleApiClient(BibleApiClient):
    def __init__(self):
        self.client = BibleApiClient()
        self.logger = logging.getLogger()
        self.cache = SimpleCache()

    def get(self, relative_path: str):
        return self.cache.get(relative_path,
                              super(FileCachedBibleApiClient, self).get)

