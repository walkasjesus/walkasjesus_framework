import json
import logging
from pathlib import Path


class SimpleCache:
    def __init__(self, cache_path: Path = Path('cache.json')):
        self._cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_items_not_persisted = 0
        self.cache_path = cache_path
        self.logger = logging.getLogger()
        self.load_state()

    def get(self, get_function, arguments):
        if arguments not in self._cache:
            self.cache_misses += 1
            self.cache_items_not_persisted += 1
            value = get_function(arguments)
            # Stringify when storing, otherwise we run into problems
            # when serializing to disk, where json serializer make int 5 a string '5'
            # which will be seen as something different when reloading the data.
            self._cache[str(arguments)] = value
        else:
            self.cache_hits += 1

        return self._cache[str(arguments)]

    def __contains__(self, item):
        return item in self._cache

    def clear_key(self, key: str):
        del self._cache[key]

    def cached_keys(self) -> [str]:
        return list(self._cache.keys())

    def load_state(self,):
        """" Load the cache content from disk. """
        if not self.cache_path.exists():
            self.logger.info(f'Could not find cache at {self.cache_path}')
            return

        with self.cache_path.open() as file:
            self._cache = json.load(file)

    def store_state(self):
        """" Store the cache content to disk. """
        with self.cache_path.open('w+') as file:
            json.dump(self._cache, file, indent=4)
            self.cache_items_not_persisted = 0
