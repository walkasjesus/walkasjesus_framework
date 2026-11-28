import json
import logging
import re

from bible_lib.bible import Bible
from bible_lib.bible_api.cached_bible_api_client import CachedBibleApiClient
from bible_lib.bible_api.query_builder import QueryBuilder
from bible_lib.bible_books import BibleBooks
from bible_lib.formatters.formatter import Formatter
from bible_lib.formatters.plain_text_formatter import PlainTextFormatter
from bible_lib.verse import Verse


class ApiBible(Bible):
    def __init__(self, api_key: str, bible_id=None, text_formatter: Formatter = PlainTextFormatter()):
        super().__init__(bible_id)
        self.client = CachedBibleApiClient(api_key)
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
            json_content = json.loads(response)
            verses_html = json_content['data']['content']
            if not self.copyright:
                self.copyright = json_content['data']['copyright']
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

    def chapter_passage_url(self, book: BibleBooks, chapter: int, last_verse: int) -> str:
        """Return the passage url that covers verses 1..last_verse of a chapter."""
        return self.query_builder.get_verses(self.id, book, chapter, 1, chapter, last_verse)

    def passage_verses(self, book: BibleBooks, chapter: int, start_verse: int, end_verse: int) -> list[Verse]:
        """Retrieve a passage while preserving the provider's combined verse ranges."""
        url = self.query_builder.get_verses(self.id, book, chapter, start_verse, chapter, end_verse)
        json_content = json.loads(self.client.get(url))
        data = json_content['data']
        if not self.copyright:
            self.copyright = data.get('copyright', '')
        return self.extract_verses(book, chapter, data['content'])

    def chapter_verses(self, book: BibleBooks, chapter: int, last_verse: int, force_refresh: bool = False) -> dict:
        """Retrieve verses 1..last_verse of a chapter with a single passage request.

        Returns a mapping of verse number to verse text. Unlike verses(), failures
        raise so callers can fall back to per-verse retrieval.
        """
        url = self.chapter_passage_url(book, chapter, last_verse)
        response = self.client.refresh(url) if force_refresh else self.client.get(url)
        json_content = json.loads(response)
        verses_html = json_content['data']['content']
        if not self.copyright:
            self.copyright = json_content['data'].get('copyright', '')
        return {
            verse.verse: verse.text
            for verse in self.extract_verses(book, chapter, verses_html)
            if verse.chapter == chapter
        }

    def extract_verses(self, book: BibleBooks, start_chapter: int, verses_text: str) -> [Verse]:
        parsed_verses = []
        current_chapter = start_chapter

        # Format when using content-type=text is like [1] text... [2] ... [1] ...
        normalized_text = re.sub(r'\s+', ' ', verses_text).replace('\n', '')
        markers = list(re.finditer(r'\[(\d+)(?:\s*[-\u2013\u2014]\s*(\d+))?\]\s*', normalized_text))

        for index, marker in enumerate(markers):
            current_verse = int(marker.group(1))
            end = markers[index + 1].start() if index + 1 < len(markers) else len(normalized_text)
            text = normalized_text[marker.end():end].strip()
            if not text:
                continue
            if current_verse == 1 and parsed_verses:
                current_chapter += 1
            parsed_verses.append(Verse(
                book, current_chapter, current_verse, text,
                end_verse=int(marker.group(2)) if marker.group(2) else current_verse))

        return parsed_verses

    def __str__(self):
        return self.name
