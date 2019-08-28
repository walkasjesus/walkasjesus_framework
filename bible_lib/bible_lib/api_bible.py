import json
import logging
import re

from bible_lib.bible import Bible
from bible_lib.bible_books import BibleBooks
from bible_lib.formatters.formatter import Formatter
from bible_lib.formatters.plain_text_formatter import PlainTextFormatter
from bible_lib.services import Services
from bible_lib.verse import Verse


class ApiBible(Bible):
    def __init__(self, bible_id=None, text_formatter: Formatter = PlainTextFormatter()):
        self.id = bible_id
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
            verses_html = json.loads(response)['data']['content']
        except Exception as ex:
            self.logger.warning(f'Failed to parse {verse_query} for bible {self.id}.')
            self.logger.warning(ex)
            return 'Not found'

        try:
            for verse in self.extract_verses(book, start_chapter, verses_html):
                self.formatter.add_verse(verse)
        except Exception as ex:
            self.logger.warning(f'Failed to parse verse beginning at {book} {start_chapter}')
            self.logger.warning(ex)
            return 'Could not read text'

        return self.formatter.flush()

    def extract_verses(self, book: BibleBooks, start_chapter: int, verses_html: str) -> [Verse]:
        parsed_verses = []
        current_chapter = start_chapter

        # Format is like this:
        #  <p class="p"><span data-number="51" class="v">51</span>...text...</p>
        #  <p class="p"><span data-number="1" class="v">1</span>...text...</p>
        verses_html = verses_html.replace('</p>', '')
        split_verses_html = verses_html.split('<p class="p">')

        # extract verse number and texts
        for verse_html in split_verses_html:
            capture_groups = re.match(r'<span data-number="\d+" class="v">(\d+)<\/span>(.+)', verse_html)
            if capture_groups:
                current_verse = int(capture_groups.group(1))
                text = capture_groups.group(2)

                if current_verse == 1:
                    current_chapter += 1
                parsed_verses.append(Verse(book, current_chapter, current_verse, text))

        return parsed_verses

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
