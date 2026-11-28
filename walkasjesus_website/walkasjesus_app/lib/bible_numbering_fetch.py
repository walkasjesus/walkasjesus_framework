"""Budgeted acquisition using provider references, independent of study mappings."""
import json
import logging
import time
from collections import defaultdict

import requests
from bible_lib.simple_cache import SimpleCache

from walkasjesus_app.lib.bible_display_limits import max_verses_for_bible_id
from walkasjesus_app.lib.bible_numbering_checks import (
    _BOOK_CODES, _MARKER, _expiry_status, _parse_range, _risk_cases, scan_numbering_cache,
)


class RequestBudgetReached(Exception):
    pass


class NumberingSourceError(Exception):
    def __init__(self, message, stop_acquisition=False):
        super().__init__(message)
        self.stop_acquisition = stop_acquisition


class NumberingSourceFetcher:
    def __init__(self, cache_path, api_key, max_requests=100, sleep_seconds=0.5, ttl_seconds=25 * 86400):
        self.cache = SimpleCache(cache_path, ttl_seconds=ttl_seconds)
        self.api_key = api_key
        self.max_requests = max_requests
        self.sleep_seconds = sleep_seconds
        self.requests_made = 0
        self.session = requests.Session()

    def close(self):
        self.session.close()

    def get_data(self, relative_url, expected_type):
        url = 'https://api.scripture.api.bible/v1/' + relative_url
        cached = self.cache._cache.get(url)
        if _expiry_status(cached, time.time(), self.cache.ttl_seconds) == 'fresh':
            try:
                data = json.loads(cached['value'])['data']
                if isinstance(data, expected_type):
                    return data
            except (KeyError, TypeError, ValueError) as error:
                logging.getLogger(__name__).warning('Replacing invalid cached source response for %s: %s', relative_url, error)
            else:
                logging.getLogger(__name__).warning('Replacing cached source response of wrong type for %s.', relative_url)
        if self.requests_made >= self.max_requests:
            raise RequestBudgetReached()
        if not self.api_key:
            raise NumberingSourceError('BIBLE_API_KEY is required to fetch missing source data.')
        if self.requests_made and self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        self.requests_made += 1
        try:
            response = self.session.get(
                url, headers={'api-key': self.api_key}, timeout=20, allow_redirects=False)
        except requests.RequestException as error:
            raise NumberingSourceError(f'API.Bible transport failure ({type(error).__name__}).') from error
        if response.status_code != 200:
            raise NumberingSourceError(
                f'API.Bible HTTP {response.status_code} for {relative_url}.',
                stop_acquisition=response.status_code in {401, 403, 429})
        try:
            payload = response.json()
            data = payload['data']
        except (KeyError, TypeError, ValueError) as error:
            raise NumberingSourceError(f'Invalid API.Bible response for {relative_url}.') from error
        if not isinstance(data, expected_type):
            raise NumberingSourceError(f'Unexpected API.Bible data type for {relative_url}.')
        # Reload before storing, so other completed cache writes are not replaced
        # by the snapshot loaded at the start of a potentially long run.
        self.cache.load_state()
        self.cache.set_value(url, response.text)
        return data

    def acquire(self, bible_ids, books):
        initial = scan_numbering_cache(
            self.cache.cache_path, set(bible_ids), max_ttl_seconds=self.cache.ttl_seconds,
            include_source_references=True, books=books)
        available = {
            result['bible_id']: {tuple(ref) for ref in result['source_references']}
            for result in initial['bibles']
        }
        result = {'requests': 0, 'budget_exhausted': False, 'errors': [], 'skipped': []}
        risks = {book: cases for book in books if (cases := _risk_cases(book))}
        if not risks:
            return result
        try:
            for bible_id in bible_ids:
                if max_verses_for_bible_id(bible_id) is not None:
                    result['skipped'].append(
                        f'{bible_id}: licence-limited translations are not automatically prefetched.')
                    continue
                try:
                    catalogue = self.get_data(f'bibles/{bible_id}/books', list)
                    book_ids = self._ids(catalogue)
                    for book, cases in risks.items():
                        code = _BOOK_CODES[book]
                        if code not in book_ids:
                            continue
                        required = defaultdict(set)
                        for _label, candidates in cases:
                            for _code, chapter, verse in candidates:
                                if verse:
                                    required[chapter].add(verse)
                        chapters = self.get_data(f'bibles/{bible_id}/books/{code}/chapters', list)
                        chapter_ids = self._ids(chapters)
                        for chapter, candidate_verses in sorted(required.items()):
                            chapter_id = f'{code}.{chapter}'
                            if chapter_id not in chapter_ids:
                                continue
                            verses = self.get_data(f'bibles/{bible_id}/chapters/{chapter_id}/verses', list)
                            source_verses = set()
                            for verse_id in self._ids(verses):
                                try:
                                    first, last = _parse_range(verse_id)
                                except ValueError as error:
                                    raise NumberingSourceError(f'Invalid provider verse ID: {verse_id}.') from error
                                if first[:2] != (code, chapter) or last[:2] != (code, chapter):
                                    raise NumberingSourceError(f'Invalid provider verse ID: {verse_id}.')
                                source_verses.update(range(first[2], last[2] + 1))
                            missing = sorted(
                                verse for verse in candidate_verses & source_verses
                                if (code, chapter, verse) not in available.get(bible_id, set()))
                            for start, end in self._ranges(missing):
                                reference = f'{code}.{chapter}.{start}-{code}.{chapter}.{end}'
                                passage = self.get_data(
                                    f'bibles/{bible_id}/passages/{reference}?content-type=text', dict)
                                content = passage.get('content')
                                if not isinstance(content, str) or not _MARKER.search(content):
                                    raise NumberingSourceError(f'No text verse markers for {bible_id} {reference}.')
                except NumberingSourceError as error:
                    result['errors'].append(f'{bible_id}: {error}')
                    if error.stop_acquisition:
                        break
        except RequestBudgetReached:
            result['budget_exhausted'] = True
        result['requests'] = self.requests_made
        return result

    @staticmethod
    def _ids(data):
        if not data or any(not isinstance(item, dict) or not isinstance(item.get('id'), str) for item in data):
            raise NumberingSourceError('Empty or invalid provider catalogue.')
        return {item['id'] for item in data}

    @staticmethod
    def _ranges(verses):
        if not verses:
            return
        start = previous = verses[0]
        for verse in verses[1:]:
            if verse != previous + 1 or verse - start >= 200:
                yield start, previous
                start = verse
            previous = verse
        yield start, previous
