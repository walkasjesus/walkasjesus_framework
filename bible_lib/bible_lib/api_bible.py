import json
import logging

from bible_lib.bible import Bible
from bible_lib.bible_books import BibleBooks
from bible_lib.formatters.formatter import Formatter
from bible_lib.formatters.plain_text_formatter import PlainTextFormatter
from bible_lib.services import Services


class ApiBible(Bible):
    def __init__(self, bible_id=None, text_formatter: Formatter=PlainTextFormatter()):
        self.id = bible_id
        self.name = ''
        self.language = ''
        self.client = Services().api_client
        self.formatter = text_formatter
        self.logger = logging.getLogger()

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:
        book_id = self._get_book_id(book)
        verse_query = f'{book_id}.{start_chapter}.{start_verse}-{book_id}.{end_chapter}.{end_verse}'
        url = f'bibles/{self.id}/passages/{verse_query}'
        try:
            response = self.client.get(url)
        except Exception as ex:
            self.logger.warning(f'Failed to retrieve {verse_query} for bible {self.id}.')
            self.logger.warning(ex)
            return 'Not found'

        try:
            verses = json.loads(response)['data']['content']
        except Exception as ex:
            self.logger.warning(f'Failed to parse {verse_query} for bible {self.id}.')
            self.logger.warning(ex)
            return 'Not found'

        # TODO split the data like:<p class="p"><span data-number="51" class="v">51</span>En Hij sprak tot hem: Voorwaar, voorwaar, Ik zeg u: Gij zult de hemel geopend zien, en de engelen Gods zien opstijgen en nederdalen over den Mensenzoon.</p><p class="p"><span data-number="1" class="v">1</span>En de derde dag werd er een bruiloft gevierd te Kana van Galilea. De moeder van Jesus was er tegenwoordig, </p>
        # This is the idea after the split
        for verse in verses:
            self.formatter.add_verse(current_chapter,
                                     current_verse,
                                     self._get(book, current_chapter, current_verse))

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
            BibleBooks.Tobit : 'TOB',
            BibleBooks.Judith : 'JDT',
            BibleBooks.Job: 'JOB',
            BibleBooks.Psalms: 'PSA',
            BibleBooks.Proverbs: 'PRO',
            BibleBooks.Ecclesiastes: 'ECC',
            BibleBooks.SongOfSolomon: 'SNG',
            BibleBooks.Wisdom : 'WIS',
            BibleBooks.Sirach : 'SIR',
            BibleBooks.Isaiah: 'ISA',
            BibleBooks.Jeremiah: 'JER',
            BibleBooks.Lamentations: 'LAM',
            BibleBooks.Baruch : 'BAR',
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

        return mapping[book]

    def __str__(self):
        return self.name
