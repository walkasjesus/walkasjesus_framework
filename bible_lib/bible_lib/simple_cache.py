import json
import logging
from pathlib import Path


class SimpleCache:
    def __init__(self):
        self._cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_items_not_persisted = 0
        self.logger = logging.getLogger()

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

    def load_state(self, file_path: Path):
        """" Load the cache content from disk. """
        if not file_path.exists():
            self.logger.warning(f'Could not find cache at {file_path}')
            return

        with file_path.open() as file:
            self._cache = json.load(file)

    def store_state(self, file_path: Path):
        """" Store the cache content to disk. """
        with file_path.open('w+') as file:
            json.dump(self._cache, file)
            self.cache_items_not_persisted = 0
