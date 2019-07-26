import json

from bible_books import BibleBooks
from cached_bible_api_client import CachedBibleApiClient


class Bible:
    def __init__(self, bible_id=None):
        self.id = bible_id
        self.name = ''
        self.language = ''
        self.client = CachedBibleApiClient()

    def verse(self,
              book:
              BibleBooks,
              chapter: int,
              verse: int) -> str:
        book_id = self._get_book_id(book)
        url = f'bibles/{self.id}/verses/{book_id}.{chapter}.{verse}'
        response_string = self.client.get(url)
        verse = json.loads(response_string)['data']
        return verse['content']

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:
        book_id = self._get_book_id(book)
        verse_query = f'{book_id}.{start_chapter}.{start_verse}-{end_chapter}.{end_verse}'
        url = f'bibles/{self.id}/search?query={verse_query}'
        response_string = self.client.get(url)
        data = json.loads(response_string)['data']
        verses = data['passages'][0]['content']
        return verses

    def _get_book_id(self, book: BibleBooks) -> str:
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
            # BibleBooks. : 'TOB',
            # BibleBooks. : 'JDT',
            BibleBooks.Job: 'JOB',
            BibleBooks.Psalms: 'PSA',
            BibleBooks.Proverbs: 'PRO',
            BibleBooks.Ecclesiastes: 'ECC',
            BibleBooks.SongOfSolomon: 'SNG',
            # BibleBooks. : 'WIS',
            # BibleBooks. : 'SIR',
            BibleBooks.Isaiah: 'ISA',
            BibleBooks.Jeremiah: 'JER',
            BibleBooks.Lamentations: 'LAM',
            # BibleBooks. : 'BAR',
            BibleBooks.Ezekiel: 'EZK',
            BibleBooks.Daniel: 'DAG',
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
            # BibleBooks. : '1MA',
            # BibleBooks. : '2MA',
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

        return mapping[book]

    def __str__(self):
        return self.name
