from bible_lib.bible_books import BibleBooks


class QueryBuilder:
    def __init__(self):
        self.server_url = 'https://api.scripture.api.bible/'
        self.api_version = 'v1'
        self.content_type = 'text'

    def build_url(self, relative_path):
        return '{}/{}/{}'.format(self.server_url.rstrip('/'), self.api_version, relative_path.strip('/'))

    def get_bibles(self):
        return self.build_url('bibles')

    def get_verses(self,
                   bible_id,
                   book: BibleBooks,
                   start_chapter: int,
                   start_verse: int,
                   end_chapter: int,
                   end_verse: int) -> str:
        book_id = self._get_book_id(bible_id, book)
        verse_query = f'{book_id}.{start_chapter}.{start_verse}-{book_id}.{end_chapter}.{end_verse}'

        return self.build_url(f'bibles/{bible_id}/passages/{verse_query}?content-type={self.content_type}')

    def _get_book_id(self, bible_id: str, book: BibleBooks) -> str:
        """" Convert the bible book enum to the id used on the bible api. """
        # For some reason not all bibles on the bible api follow the same index convention,
        # This is a list of bibles that use a different index for specific books.
        bibles_following_alternative_daniel_key = ['9879dbb7cfe39e4d-01',
                                                   '9879dbb7cfe39e4d-02',
                                                   '9879dbb7cfe39e4d-03',
                                                   '7142879509583d59-01',
                                                   '7142879509583d59-02',
                                                   '7142879509583d59-03',
                                                   'ead7b4cc5007389c-01']

        if book == BibleBooks.Daniel and bible_id in bibles_following_alternative_daniel_key:
            return 'DAG'

        return BibleBooks.abbreviation(book)

