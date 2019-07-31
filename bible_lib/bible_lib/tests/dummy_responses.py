from pathlib import Path


class DummyResponses:
    def __init__(self):
        self.directory = Path('data')

    def bibles(self):
        return self._load('bibles_response.txt')

    def books(self):
        return self._load('books_response.txt')

    def chapters(self):
        return self._load('chapters_response.txt')

    def verses(self):
        return self._load('passages_response.txt')

    def _load(self, file_name: str):
        file_path = self.directory / file_name

        with file_path.open(encoding='utf-8') as file:
            return file.read().replace('\n', '')
