import json
import logging
import re

from bible_lib.bible import Bible
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_books import BibleBooks
from bible_lib.formatters.formatter import Formatter
from bible_lib.formatters.plain_text_formatter import PlainTextFormatter
from bible_lib.bible_api.services import Services
from bible_lib.verse import Verse


class ApiBible(Bible):
    def __init__(self, bible_id=None, text_formatter: Formatter = PlainTextFormatter()):
        self.id = bible_id
        self.client = Services().api_client
        self.formatter = text_formatter
        self.query_builder = QueryBuilder()
        self.logger = logging.getLogger()

    def verses(self,
               book: BibleBooks,
               start_chapter: int,
               start_verse: int,
               end_chapter: int,
               end_verse: int) -> str:
        verses_str = f'{book}{start_chapter}{start_verse}-{end_chapter}{end_chapter}'
        url = self.query_builder.get_verses(self.id, book, start_chapter, start_verse, end_chapter, end_verse)

        try:
            response = self.client.get(url)
        except Exception as ex:
            self.logger.warning(f'Failed to retrieve {verses_str} for bible {self.id}.')
            self.logger.warning(ex)
            return 'Not found'

        try:
            verses_html = json.loads(response)['data']['content']
        except Exception as ex:
            self.logger.warning(f'Failed to parse {verses_str} for bible {self.id}.')
            self.logger.warning(ex)
            return 'Not found'

        try:
            for verse in self.extract_verses(book, start_chapter, verses_html):
                self.formatter.add_verse(verse)
        except Exception as ex:
            self.logger.warning(f'Failed to parse {verses_str}')
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

    def __str__(self):
        return self.name
