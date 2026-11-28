import os

from bible_lib.bible_api.bible_api_client import BibleApiClient
from bible_lib.bible_api.services import Services


class CachedBibleApiClient(BibleApiClient):
    def __init__(self, api_key: str):
        super(CachedBibleApiClient, self).__init__(api_key)
        self.cache = Services().cache

    def get(self, url: str):
        return self.cache.get(super(CachedBibleApiClient, self).get, url)

    def refresh(self, url: str):
        """Force a fresh retrieval of the url, replacing any cached entry."""
        if os.environ.get('BIBLE_API_OFFLINE') == '1':
            raise RuntimeError('Refreshing API.Bible content is disabled in cache-only mode.')
        self.cache.clear_key(url)
        return self.get(url)
