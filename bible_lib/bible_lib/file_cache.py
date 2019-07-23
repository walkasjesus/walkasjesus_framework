import json
from pathlib import Path


class FileCache:
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._cache = {}

    def get(self, key):
        return self._cache[key]

    def set(self, key, value):
        self._cache[key] = value

    def load_state(self):
        """" Load the cache content from disk. """
        with self.file_path.open() as file:
            self._cache = json.load(file)

    def store_state(self):
        """" Store the cache content to disk. """
        with self.file_path.open('w+') as file:
            json.dump(self._cache, file)
