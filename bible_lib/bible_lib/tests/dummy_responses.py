class DummyResponses:
    def bibles(self):
        return self._load('bibles_response.txt')

    def books(self):
        return self._load('books_response.txt')

    def _load(self, file_name: str):
        with open(file_name, encoding='utf-8') as file:
            return file.read().replace('\n', '')
