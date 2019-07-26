import json
from pathlib import Path


class SimpleCache:
    def __init__(self):
        self._cache = {}
        self.cache_items_not_persisted = 0

    def get(self, get_function, arguments):
        if arguments not in self._cache:
            self.cache_items_not_persisted += 1
            value = get_function(arguments)
            # Stringify when storing, otherwise we run into problems
            # when serializing to disk, where json serializer make int 5 a string '5'
            # which will be seen as something different when reloading the data.
            self._cache[str(arguments)] = value

        return self._cache[str(arguments)]

    def load_state(self, file_path: Path):
        """" Load the cache content from disk. """
        with file_path.open() as file:
            self._cache = json.load(file)

    def store_state(self, file_path: Path):
        """" Store the cache content to disk. """
        with file_path.open('w+') as file:
            json.dump(self._cache, file)
            self.cache_items_not_persisted = 0
