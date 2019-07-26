class DummyResponses:
    def bibles(self):
        return self._load('bibles_response.txt')

    def books(self):
        return self._load('books_response.txt')

    def chapters(self):
        return self._load('chapters_response.txt')

    def verses(self):
        """"Note, even though called verses, the api only returns a single verse. """
        return self._load('verses_response.txt')

    def search_verses(self):
        """"Using the search api, we can lookup things like search?query=JHN.3.51-4.1. """
        return self._load('search_verses_response.txt')

    def _load(self, file_name: str):
        with open(file_name, encoding='utf-8') as file:
            return file.read().replace('\n', '')
