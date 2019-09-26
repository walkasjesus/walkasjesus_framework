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
        mapping = {
            BibleBooks.Genesis: 'GEN',
            BibleBooks.Exodus: 'EXO',
            BibleBooks.Leviticus: 'LEV',
            BibleBooks.Numbers: 'NUM',
            BibleBooks.Deuteronomy: 'DEU',
            BibleBooks.Joshua: 'JOS',
            BibleBooks.Judges: 'JDG',
            BibleBooks.Ruth: 'RUT',
            BibleBooks.SamuelFirstBook: '1SA',
            BibleBooks.SamuelSecondBook: '2SA',
            BibleBooks.KingsFirstBook: '1KI',
            BibleBooks.KingsSecondBook: '2KI',
            BibleBooks.ChroniclesFirstBook: '1CH',
            BibleBooks.ChroniclesSecondBook: '2CH',
            BibleBooks.Ezra: 'EZR',
            BibleBooks.Nehemiah: 'NEH',
            BibleBooks.Tobit: 'TOB',
            BibleBooks.Judith: 'JDT',
            BibleBooks.Job: 'JOB',
            BibleBooks.Psalms: 'PSA',
            BibleBooks.Proverbs: 'PRO',
            BibleBooks.Ecclesiastes: 'ECC',
            BibleBooks.SongOfSolomon: 'SNG',
            BibleBooks.Wisdom: 'WIS',
            BibleBooks.Sirach: 'SIR',
            BibleBooks.Isaiah: 'ISA',
            BibleBooks.Jeremiah: 'JER',
            BibleBooks.Lamentations: 'LAM',
            BibleBooks.Baruch: 'BAR',
            BibleBooks.Ezekiel: 'EZK',
            BibleBooks.Daniel: 'DAN',
            BibleBooks.Hosea: 'HOS',
            BibleBooks.Joel: 'JOL',
            BibleBooks.Amos: 'AMO',
            BibleBooks.Obadiah: 'OBA',
            BibleBooks.Jonah: 'JON',
            BibleBooks.Micah: 'MIC',
            BibleBooks.Nahum: 'NAM',
            BibleBooks.Habakkuk: 'HAB',
            BibleBooks.Zephaniah: 'ZEP',
            BibleBooks.Haggai: 'HAG',
            BibleBooks.Zechariah: 'ZEC',
            BibleBooks.Malachi: 'MAL',
            BibleBooks.MaccabeesFirstBook: '1MA',
            BibleBooks.MaccabeesSecondBook: '2MA',
            BibleBooks.Matthew: 'MAT',
            BibleBooks.Mark: 'MRK',
            BibleBooks.Luke: 'LUK',
            BibleBooks.John: 'JHN',
            BibleBooks.Acts: 'ACT',
            BibleBooks.Romans: 'ROM',
            BibleBooks.CorinthiansFirstBook: '1CO',
            BibleBooks.CorinthiansSecondBook: '2CO',
            BibleBooks.Galatians: 'GAL',
            BibleBooks.Ephesians: 'EPH',
            BibleBooks.Philippians: 'PHP',
            BibleBooks.Colossians: 'COL',
            BibleBooks.ThessaloniansFirstBook: '1TH',
            BibleBooks.ThessaloniansSecondBook: '2TH',
            BibleBooks.TimothyFirstBook: '1TI',
            BibleBooks.TimothySecondBook: '2TI',
            BibleBooks.Titus: 'TIT',
            BibleBooks.Philemon: 'PHM',
            BibleBooks.Hebrews: 'HEB',
            BibleBooks.James: 'JAS',
            BibleBooks.PeterFirstBook: '1PE',
            BibleBooks.PeterSecondBook: '2PE',
            BibleBooks.JohnFirstBook: '1JN',
            BibleBooks.JohnSecondBook: '2JN',
            BibleBooks.JohnThirdBook: '3JN',
            BibleBooks.Jude: 'JUD',
            BibleBooks.Revelation: 'REV'}

        # For some reason not all bibles on the bible api follow the same index convention,
        # This is a list of bibles that use a different index for specific books.
        bibles_following_alternative_daniel_key = ['de4e12af7f28f599-01',
                                                   '9879dbb7cfe39e4d-01',
                                                   '9879dbb7cfe39e4d-02',
                                                   '9879dbb7cfe39e4d-03',
                                                   '7142879509583d59-01',
                                                   '7142879509583d59-02',
                                                   '7142879509583d59-03',
                                                   'ead7b4cc5007389c-01']

        if book == BibleBooks.Daniel and bible_id in bibles_following_alternative_daniel_key:
            return 'DAG'

        return mapping[book]

