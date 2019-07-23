import logging

from bible_api_client import BibleApiClient
from file_cache import FileCache


class FileCachedBibleApiClient(BibleApiClient):
    def __init__(self):
        self.client = BibleApiClient()
        self.logger = logging.getLogger()
        self.cache = FileCache()


    def get(self, relative_path: str):
        if not self.cache.contains(relative_path):
            result = super(FileCachedBibleApiClient, self).get()
            self.cache.set(relative_path, result)

        return self.cache.get(relative_path)
