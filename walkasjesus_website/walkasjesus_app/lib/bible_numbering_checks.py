"""Structural checks of fresh API.Bible cache entries; never fetch Bible text."""
import hashlib
import inspect
import json
import math
import re
import time
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from bible_lib.bible_books import BibleBooks


_REFERENCE = re.compile(r'^([A-Z0-9]+)\.(\d+)\.(\d+)$')
_MARKER = re.compile(r'\[(\d+)(?:\s*[-\u2013\u2014]\s*(\d+))?\]')
_CACHE_PATH = re.compile(r'^/v1/bibles/([^/]+)/passages/([^/]+)$')
_BOOK_CODES = {book.name: BibleBooks.abbreviation(book) for book in BibleBooks}


@lru_cache(maxsize=1)
def numbering_mapping_revision():
    from django.conf import settings
    from bible_lib.bible_api.api_bible import ApiBible
    from walkasjesus_app.lib.strongs_service import _hebrew_verse_index, _STEPBIBLE_OT_FILES, _stepbible_file_for_book
    from walkasjesus_app.models.bibles import LocalStatenvertalingBible, local_bible_root
    from walkasjesus_app.views.bible_study_view import _study_numbering_profile, _study_verse_references

    code = '\n'.join(inspect.getsource(function) for function in (
        _study_numbering_profile, _study_verse_references, _hebrew_verse_index, ApiBible.extract_verses,
        LocalStatenvertalingBible.psalm_study_verse,
        LocalStatenvertalingBible._chapters,
    ))
    code += repr(sorted(getattr(settings, 'BIBLE_ABBREVIATION_OVERRIDES', {}).items()))
    digest = hashlib.sha256(code.encode())
    paths = {_stepbible_file_for_book(book) for book in _STEPBIBLE_OT_FILES}
    paths.update((local_bible_root() / LocalStatenvertalingBible.DATA_KEY).glob('*.json.gz'))
    for path in sorted(paths):
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
    return digest.hexdigest()


def _risk_cases(book):
    from walkasjesus_app.lib.strongs_service import _hebrew_verse_index

    code = _BOOK_CODES[book]
    cases = []
    for hebrew, english in sorted(_hebrew_verse_index(book)[1].items()):
        if english == {hebrew}:
            continue
        candidates = {(code, *hebrew)} | {(code, *source) for source in english}
        cases.append((f'{code}.{hebrew[0]}.{hebrew[1]}', candidates))
    return cases


def _parse_range(value):
    parts = value.split('-')
    if len(parts) not in (1, 2):
        raise ValueError('Invalid cached passage range.')
    refs = []
    for part in parts:
        match = _REFERENCE.fullmatch(part)
        if match is None:
            raise ValueError('Invalid cached passage reference.')
        refs.append((match[1], int(match[2]), int(match[3])))
    start, end = refs[0], refs[-1]
    if start[0] != end[0] or start[1:] > end[1:]:
        raise ValueError('Unsupported cross-book or reversed passage range.')
    if any(not 1 <= ref[1] <= 200 or not 0 <= ref[2] <= 1000 for ref in refs):
        raise ValueError('Cached passage reference is outside supported bounds.')
    return start, end


def _expiry_status(entry, now, max_ttl_seconds):
    expiry = entry.get('expires_at') if isinstance(entry, dict) else None
    if not isinstance(expiry, (int, float)) or not math.isfinite(expiry):
        return 'unknown_expiry'
    if expiry <= now:
        return 'expired'
    if expiry > now + max_ttl_seconds:
        return 'untrusted_ttl'
    return 'fresh'


def scan_numbering_cache(cache_path: Path, bible_ids=None, now=None, max_ttl_seconds=25 * 86400):
    now = time.time() if now is None else now
    with cache_path.open(encoding='utf-8') as handle:
        entries = json.load(handle)
    if not isinstance(entries, dict):
        raise ValueError('The API.Bible cache must be a JSON object.')

    reports = {}
    boundaries = defaultdict(lambda: defaultdict(set))
    books_by_bible = {}
    chapters_by_bible = defaultdict(dict)
    cache_warnings = []
    for key, entry in entries.items():
        url = urlsplit(str(key))
        if url.hostname not in {'api.scripture.api.bible', 'api.bible'}:
            continue
        path = unquote(url.path)
        match = _CACHE_PATH.fullmatch(path)
        if not match:
            # Fresh book catalogues can establish that an OT check is inapplicable.
            catalogue = re.fullmatch(r'/v1/bibles/([^/]+)/books(?:/([A-Z0-9]+)/chapters)?', path)
            if catalogue and isinstance(entry, dict):
                if _expiry_status(entry, now, max_ttl_seconds) == 'fresh':
                    try:
                        data = json.loads(entry['value'])['data']
                        if not isinstance(data, list) or not data:
                            raise ValueError('The cached catalogue is empty or not a list.')
                        ids = [item['id'] for item in data]
                        if not all(isinstance(item, str) for item in ids):
                            raise ValueError('The cached catalogue contains invalid IDs.')
                        if catalogue[2]:
                            chapter_ids = set()
                            for item in ids:
                                chapter_match = re.fullmatch(r'([A-Z0-9]+)\.(\d+)', item)
                                if chapter_match is None or chapter_match[1] != catalogue[2]:
                                    raise ValueError('Invalid cached chapter ID.')
                                chapter_ids.add(int(chapter_match[2]))
                            chapters_by_bible[catalogue[1]][catalogue[2]] = chapter_ids
                        else:
                            books_by_bible[catalogue[1]] = set(ids)
                    except (KeyError, TypeError, ValueError) as error:
                        cache_warnings.append(f'Invalid cached catalogue for {catalogue[1]}: {error}')
            continue
        bible_id, requested = match.groups()
        if bible_ids is not None and bible_id not in bible_ids:
            continue
        report = reports.setdefault(bible_id, {
            'bible_id': bible_id, 'entries': Counter(), 'findings': [], 'merged_groups': set(),
        })
        expiry_status = _expiry_status(entry, now, max_ttl_seconds)
        if expiry_status != 'fresh':
            report['entries'][expiry_status] += 1
            continue
        report['entries']['fresh'] += 1
        try:
            start, end = _parse_range(requested)
            data = json.loads(entry['value'])['data']
            text = data['content']
            if not isinstance(text, str):
                raise ValueError('Cached passage content is not text.')
            if parse_qs(url.query).get('content-type') != ['text']:
                report['entries']['unsupported_format'] += 1
                continue
            markers = list(_MARKER.finditer(text))
            if not markers:
                raise ValueError('No verse markers found in the cached passage.')
        except (KeyError, TypeError, ValueError) as error:
            report['findings'].append({'kind': 'invalid_entry', 'reference': requested, 'detail': str(error)})
            continue

        chapter, previous_end = start[1], -1
        observed = set()
        for index, marker in enumerate(markers):
            first, last = int(marker[1]), int(marker[2] or marker[1])
            if first == 1 and previous_end >= 1 and chapter < end[1]:
                chapter += 1
                previous_end = -1
            if last < first or last > 1000 or first <= previous_end:
                report['findings'].append({
                    'kind': 'overlapping_or_reversed_markers', 'reference': requested,
                    'detail': f'{start[0]}.{chapter}.{first}-{last}',
                })
                continue
            previous_end = last
            text_end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            if not text[marker.end():text_end].strip():
                report['findings'].append({
                    'kind': 'empty_verse_text', 'reference': requested,
                    'detail': f'{start[0]}.{chapter}.{first}-{last}',
                })
                continue
            if first != last:
                report['merged_groups'].add(f'{start[0]}.{chapter}.{first}-{last}')
            for verse in range(first, last + 1):
                ref = (start[0], chapter, verse)
                observed.add(ref)
                boundaries[bible_id][ref].add((first, last))
        if start[1] == end[1]:
            missing = [
                verse for verse in range(start[2], end[2] + 1)
                if (start[0], start[1], verse) not in observed
            ]
            if missing:
                report['findings'].append({
                    'kind': 'missing_requested_verses', 'reference': requested,
                    'detail': ', '.join(map(str, missing)),
                })

    for bible_id in bible_ids or ():
        reports.setdefault(bible_id, {
            'bible_id': bible_id, 'entries': Counter(), 'findings': [], 'merged_groups': set(),
        })
    risks = {book: _risk_cases(book) for book in ('Psalms', 'Hosea', 'Joel')}
    for bible_id, report in reports.items():
        available = boundaries[bible_id]
        conflicts = [
            '.'.join(map(str, ref)) for ref, groups in available.items() if len(groups) > 1
        ]
        for ref in sorted(conflicts):
            report['findings'].append({
                'kind': 'conflicting_cached_boundaries', 'reference': ref,
                'detail': 'Overlapping cache entries give different verse boundaries; manual review is required.',
            })
        report['entries'] = dict(report['entries'])
        report['available_references'] = len(available)
        report['cached_chapters'] = len({(ref[0], ref[1]) for ref in available})
        report['chapter_catalogue_coverage'] = []
        for book, expected in sorted(chapters_by_bible[bible_id].items()):
            observed_chapters = {ref[1] for ref in available if ref[0] == book}
            report['chapter_catalogue_coverage'].append({
                'book': book, 'expected': len(expected), 'cached': len(observed_chapters & expected),
                'missing': sorted(expected - observed_chapters),
            })
            for chapter in sorted(observed_chapters - expected):
                report['findings'].append({
                    'kind': 'chapter_not_in_cached_catalogue', 'reference': f'{book}.{chapter}',
                    'detail': 'This chapter does not occur in the fresh provider chapter catalogue.',
                })
        report['merged_groups'] = sorted(report['merged_groups'])
        report['scopes'] = {}
        for book, cases in risks.items():
            scope = book.lower()
            catalogue = books_by_bible.get(bible_id)
            applicable = catalogue is None or _BOOK_CODES[book] in catalogue
            covered = [label for label, candidates in cases if any(ref in available for ref in candidates)]
            missing = [label for label, candidates in cases if not any(ref in available for ref in candidates)]
            report['scopes'][scope] = {
                'state': ('not_applicable' if not applicable else
                          'incomplete' if missing else 'requires_manual_review'),
                'expected_cases': len(cases) if applicable else 0,
                'cached_candidates': len(covered) if applicable else 0,
                'missing_examples': missing[:30] if applicable else [],
                'cached_examples': covered[:30] if applicable else [],
            }
        report['scopes']['structure'] = {
            'state': ('findings' if report['findings'] else
                      'no_structural_issues_detected' if available else 'no_data'),
            'finding_count': len(report['findings']),
        }
        report['scopes']['merged'] = {
            'state': ('requires_manual_review' if report['merged_groups'] else
                      'no_merged_groups_observed' if available else 'no_data'),
            'group_count': len(report['merged_groups']),
        }
    return {
        'api_requests': 0,
        'cache_path': str(cache_path.resolve()),
        'mapping_revision': numbering_mapping_revision(),
        'warnings': cache_warnings,
        'bibles': [reports[bible_id] for bible_id in sorted(reports)],
    }
