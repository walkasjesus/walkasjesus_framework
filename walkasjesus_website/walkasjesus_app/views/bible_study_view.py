import logging
import hashlib
import json
import re
import requests
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlencode
from collections import Counter

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views import View

from walkasjesus_app.lib.access_policy import filter_visible_bibles_for_request, is_bible_id_visible_for_request
from walkasjesus_app.lib.strongs_service import original_text_payload
from walkasjesus_app.models import BibleTranslation, UserPreferences, BibleTranslationUsageDaily
from walkasjesus_app.models.bible_books import BibleBooks

logger = logging.getLogger(__name__)

VERSE_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6))
BIBLE_SEARCH_CACHE_TIMEOUT = int(getattr(settings, 'BIBLE_STUDY_SEARCH_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 7))

_CHAPTER_INDEX_LOCK = threading.Lock()

_OT_BOOKS = {
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
    'SamuelFirstBook', 'SamuelSecondBook', 'KingsFirstBook', 'KingsSecondBook',
    'ChroniclesFirstBook', 'ChroniclesSecondBook', 'Ezra', 'Nehemiah', 'Esther', 'Job',
    'Psalms', 'Proverbs', 'Ecclesiastes', 'SongOfSolomon', 'Isaiah', 'Jeremiah',
    'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah',
    'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
}

# Maps app BibleBooks enum names to Sefaria reference names (OT only)
_SEFARIA_BOOK_NAMES = {
    'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers',
    'Deuteronomy': 'Deuteronomy', 'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth',
    'SamuelFirstBook': 'I Samuel', 'SamuelSecondBook': 'II Samuel',
    'KingsFirstBook': 'I Kings', 'KingsSecondBook': 'II Kings',
    'ChroniclesFirstBook': 'I Chronicles', 'ChroniclesSecondBook': 'II Chronicles',
    'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah', 'Esther': 'Esther', 'Job': 'Job',
    'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
    'SongOfSolomon': 'Song of Songs', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
    'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel',
    'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obadiah': 'Obadiah',
    'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk',
    'Zephaniah': 'Zephaniah', 'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi',
}

# Maps app BibleBooks enum names to Scriptura/BijbelAPI book names
_SCRIPTURA_BOOK_NAMES = {
    'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers',
    'Deuteronomy': 'Deuteronomy', 'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth',
    'SamuelFirstBook': '1 Samuel', 'SamuelSecondBook': '2 Samuel',
    'KingsFirstBook': '1 Kings', 'KingsSecondBook': '2 Kings',
    'ChroniclesFirstBook': '1 Chronicles', 'ChroniclesSecondBook': '2 Chronicles',
    'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah', 'Esther': 'Esther', 'Job': 'Job',
    'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
    'SongOfSolomon': 'Song of Solomon', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
    'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel',
    'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obadiah': 'Obadiah',
    'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk',
    'Zephaniah': 'Zephaniah', 'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi',
    'Matthew': 'Matthew', 'Mark': 'Mark', 'Luke': 'Luke', 'John': 'John', 'Acts': 'Acts',
    'Romans': 'Romans', 'CorinthiansFirstBook': '1 Corinthians', 'CorinthiansSecondBook': '2 Corinthians',
    'Galatians': 'Galatians', 'Ephesians': 'Ephesians', 'Philippians': 'Philippians',
    'Colossians': 'Colossians', 'ThessaloniansFirstBook': '1 Thessalonians',
    'ThessaloniansSecondBook': '2 Thessalonians', 'TimothyFirstBook': '1 Timothy',
    'TimothySecondBook': '2 Timothy', 'Titus': 'Titus', 'Philemon': 'Philemon',
    'Hebrews': 'Hebrews', 'James': 'James', 'PeterFirstBook': '1 Peter', 'PeterSecondBook': '2 Peter',
    'JohnFirstBook': '1 John', 'JohnSecondBook': '2 John', 'JohnThirdBook': '3 John',
    'Jude': 'Jude', 'Revelation': 'Revelation',
}

_VALID_BOOK_NAMES = {b.name for b in BibleBooks}

# Canonical Protestant Bible chapter counts (KJV).
# Used during index build so we never probe chapter existence via the API, saving quota.
_CANONICAL_CHAPTER_COUNTS = {
    'Genesis': 50, 'Exodus': 40, 'Leviticus': 27, 'Numbers': 36, 'Deuteronomy': 34,
    'Joshua': 24, 'Judges': 21, 'Ruth': 4, 'SamuelFirstBook': 31, 'SamuelSecondBook': 24,
    'KingsFirstBook': 22, 'KingsSecondBook': 25, 'ChroniclesFirstBook': 29, 'ChroniclesSecondBook': 36,
    'Ezra': 10, 'Nehemiah': 13, 'Esther': 10, 'Job': 42, 'Psalms': 150,
    'Proverbs': 31, 'Ecclesiastes': 12, 'SongOfSolomon': 8, 'Isaiah': 66, 'Jeremiah': 52,
    'Lamentations': 5, 'Ezekiel': 48, 'Daniel': 12, 'Hosea': 14, 'Joel': 3,
    'Amos': 9, 'Obadiah': 1, 'Jonah': 4, 'Micah': 7, 'Nahum': 3,
    'Habakkuk': 3, 'Zephaniah': 3, 'Haggai': 2, 'Zechariah': 14, 'Malachi': 4,
    'Matthew': 28, 'Mark': 16, 'Luke': 24, 'John': 21, 'Acts': 28,
    'Romans': 16, 'CorinthiansFirstBook': 16, 'CorinthiansSecondBook': 13,
    'Galatians': 6, 'Ephesians': 6, 'Philippians': 4, 'Colossians': 4,
    'ThessaloniansFirstBook': 5, 'ThessaloniansSecondBook': 3,
    'TimothyFirstBook': 6, 'TimothySecondBook': 4, 'Titus': 3, 'Philemon': 1,
    'Hebrews': 13, 'James': 5, 'PeterFirstBook': 5, 'PeterSecondBook': 3,
    'JohnFirstBook': 5, 'JohnSecondBook': 1, 'JohnThirdBook': 1, 'Jude': 1, 'Revelation': 22,
}

_API_BIBLE_BOOK_ORDER = {
    code: index for index, code in enumerate((
        'GEN', 'EXO', 'LEV', 'NUM', 'DEU', 'JOS', 'JDG', 'RUT', '1SA', '2SA', '1KI', '2KI',
        '1CH', '2CH', 'EZR', 'NEH', 'EST', 'JOB', 'PSA', 'PRO', 'ECC', 'SNG', 'ISA', 'JER',
        'LAM', 'EZK', 'DAN', 'HOS', 'JOL', 'AMO', 'OBA', 'JON', 'MIC', 'NAM', 'HAB', 'ZEP',
        'HAG', 'ZEC', 'MAL', 'MAT', 'MRK', 'LUK', 'JHN', 'ACT', 'ROM', '1CO', '2CO', 'GAL',
        'EPH', 'PHP', 'COL', '1TH', '2TH', '1TI', '2TI', 'TIT', 'PHM', 'HEB', 'JAS', '1PE',
        '2PE', '1JN', '2JN', '3JN', 'JUD', 'REV',
    ))
}


def _bible_dropdown_label(bible):
    language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
    bible_name = str(getattr(bible, 'name', '') or '').strip()
    return f'{language_code} - {bible_name}' if language_code else bible_name


def _bible_dropdown_sort_key(bible):
    language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
    bible_name = str(getattr(bible, 'name', '') or '').strip()
    return f'{bible_name} - {language_code}'.casefold()


def _safe_int(value, default, minimum=1):
    try:
        return max(minimum, int(value))
    except (ValueError, TypeError):
        return default


def _safe_search_limit(value):
    try:
        return max(1, min(50, int(value)))
    except (ValueError, TypeError):
        return 10


def _safe_search_offset(value):
    try:
        return max(0, int(value))
    except (ValueError, TypeError):
        return 0


def _safe_search_sort(value):
    sort = str(value or '').strip()
    return sort if sort in {'relevance', 'canonical', 'reverse-canonical'} else 'canonical'


def _safe_search_fuzziness(value):
    fuzziness = str(value or '').strip().upper()
    return fuzziness if fuzziness in {'0', '1', '2', 'AUTO'} else 'AUTO'


def _safe_search_range(value):
    search_range = str(value or '').strip().upper()
    return search_range if len(search_range) <= 200 and re.match(r'^[A-Z0-9.,\-]+$', search_range) else ''


def _bible_usage_user_identity(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        raw_identifier = f'auth:{getattr(user, "pk", "")}'
        return BibleTranslationUsageDaily.USER_AUTHENTICATED, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]

    session_key = getattr(getattr(request, 'session', None), 'session_key', None)
    if not session_key and hasattr(request, 'session'):
        request.session.save()
        session_key = request.session.session_key

    remote_addr = str(request.META.get('REMOTE_ADDR', '') or '').strip()
    user_agent = str(request.META.get('HTTP_USER_AGENT', '') or '').strip()
    raw_identifier = f'anon:{session_key or "no-session"}:{remote_addr}:{user_agent}'
    return BibleTranslationUsageDaily.USER_ANONYMOUS, hashlib.sha256(raw_identifier.encode('utf-8')).hexdigest()[:32]


def _record_bible_usage(request, bible, source, endpoint, verse_count=1, request_count=1):
    source = str(source or '').strip().lower()
    if source not in {BibleTranslationUsageDaily.SOURCE_API, BibleTranslationUsageDaily.SOURCE_CACHE}:
        return

    usage_date = timezone.now().date()
    user_kind, user_key = _bible_usage_user_identity(request)
    bible_id = str(getattr(bible, 'id', '') or '')
    if not bible_id:
        return

    language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:8]
    bible_name = str(getattr(bible, 'name', '') or '').strip()
    verse_count = max(0, int(verse_count or 0))
    request_count = max(0, int(request_count or 0))

    if verse_count == 0 and request_count == 0:
        return

    try:
        with transaction.atomic():
            row = BibleTranslationUsageDaily.objects.select_for_update().filter(
                usage_date=usage_date,
                bible_id=bible_id,
                source=source,
                endpoint=endpoint,
                user_key=user_key,
            ).first()
            if row:
                row.request_count += request_count
                row.verse_count += verse_count
                row.user_kind = user_kind
                row.bible_name = bible_name
                row.bible_language = language_code
                row.save(update_fields=['request_count', 'verse_count', 'user_kind', 'bible_name', 'bible_language', 'updated_at'])
            else:
                BibleTranslationUsageDaily.objects.create(
                    usage_date=usage_date,
                    bible_id=bible_id,
                    bible_name=bible_name,
                    bible_language=language_code,
                    source=source,
                    endpoint=endpoint,
                    user_kind=user_kind,
                    user_key=user_key,
                    request_count=request_count,
                    verse_count=verse_count,
                )
    except Exception:
        logger.exception('Failed to record bible usage metric for bible=%s source=%s endpoint=%s', bible_id, source, endpoint)


def _record_bible_usage_for_sources(request, bible, verse_sources, endpoint):
    counts = Counter(str(source or '').strip().lower() for source in (verse_sources or {}).values())
    for source, verse_count in counts.items():
        if source in {BibleTranslationUsageDaily.SOURCE_API, BibleTranslationUsageDaily.SOURCE_CACHE}:
            _record_bible_usage(
                request=request,
                bible=bible,
                source=source,
                endpoint=endpoint,
                verse_count=verse_count,
                request_count=1,
            )


def _api_bible_search_url(bible_id, query, limit, offset=0, sort='canonical', fuzziness='AUTO', search_range=''):
    params = {
        'query': str(query or '').strip(),
        'limit': limit,
        'offset': offset,
        'sort': sort,
        'fuzziness': fuzziness,
    }
    if search_range:
        params['range'] = search_range
    return f'https://api.scripture.api.bible/v1/bibles/{bible_id}/search?{urlencode(params)}'


def _api_bible_search_payload(bible_id, query, limit, offset=0, sort='canonical', fuzziness='AUTO', search_range=''):
    cache_payload = json.dumps({
        'query': str(query or '').strip(),
        'limit': limit,
        'offset': offset,
        'sort': sort,
        'fuzziness': fuzziness,
        'range': search_range,
    }, sort_keys=True)
    query_hash = hashlib.sha256(cache_payload.encode('utf-8')).hexdigest()[:24]
    cache_key = f'bible_study:search:v2:{bible_id}:{query_hash}'
    cached = None if getattr(settings, 'DISABLE_CACHE_FOR_DEBUG', False) else cache.get(cache_key)
    if cached is not None:
        return cached

    url = _api_bible_search_url(bible_id, query, limit, offset, sort, fuzziness, search_range)
    response = requests.get(url, headers={'api-key': settings.BIBLE_API_KEY}, timeout=15)
    response.raise_for_status()
    payload = response.json()
    cache.set(cache_key, payload, BIBLE_SEARCH_CACHE_TIMEOUT)
    return payload


def _search_result_canonical_key(verse):
    verse_id = str(verse.get('id') or '').strip().upper() if isinstance(verse, dict) else ''
    parts = verse_id.split('.')
    if len(parts) >= 3 and parts[0] in _API_BIBLE_BOOK_ORDER:
        try:
            return (_API_BIBLE_BOOK_ORDER[parts[0]], int(parts[1]), int(parts[2]))
        except (TypeError, ValueError):
            pass
    return (len(_API_BIBLE_BOOK_ORDER) + 1, 0, 0)


def _search_result_reference_span(verses):
    references = [
        (_search_result_canonical_key(verse), str(verse.get('reference') or '').strip())
        for verse in verses or []
        if isinstance(verse, dict) and str(verse.get('reference') or '').strip()
    ]
    if not references:
        return ''
    references.sort(key=lambda item: item[0])
    return references[0][1] if len(references) == 1 else f'{references[0][1]}–{references[-1][1]}'


def _chapter_index_path():
    configured = str(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_PATH', '') or '').strip()
    if configured:
        return Path(configured)
    return Path(getattr(settings, 'BASE_DIR', '.')) / 'data' / 'bible_study_chapter_index.json'


def _chapter_index_autobuild_enabled():
    return bool(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_AUTOBUILD', False))


def _chapter_index_live_fetch_enabled():
    return bool(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_ALLOW_LIVE_FETCH', False))


def _primary_chapter_index_bible_id():
    configured = str(getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_PRIMARY_BIBLE_ID', '') or '').strip()
    if configured:
        return configured
    return str(getattr(settings, 'DEFAULT_BIBLE_ANY_LANGUAGE', '') or '').strip()


def _load_chapter_index():
    path = _chapter_index_path()
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        logger.exception('Failed to load Bible Study chapter index from %s', path)
        return {}


def _save_chapter_index(index_payload):
    path = _chapter_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f'{path.suffix}.tmp')
    with temp_path.open('w', encoding='utf-8') as handle:
        json.dump(index_payload, handle, indent=2, sort_keys=True)
    temp_path.replace(path)


@contextmanager
def _suppress_probe_warnings():
    # bible_lib logs out-of-range probe misses as warnings on the root logger.
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    try:
        root_logger.setLevel(max(previous_level, logging.ERROR))
        yield
    finally:
        root_logger.setLevel(previous_level)


def _chapter_has_verse(bible, bible_lib_book, chapter, verse_number):
    transient_markers = (
        'connection reset',
        'connection aborted',
        'timed out',
        'temporarily unavailable',
        'service unavailable',
        'status code 502',
        'status code 503',
        'status code 504',
    )

    text = ''
    attempts = int(max(1, getattr(settings, 'BIBLE_STUDY_CHAPTER_INDEX_RETRY_ATTEMPTS', 3)))
    for attempt in range(attempts):
        try:
            with _suppress_probe_warnings():
                text = bible.verses(bible_lib_book, chapter, verse_number, chapter, verse_number)
            break
        except Exception as ex:
            message = str(ex or '').lower()
            if attempt < attempts - 1 and any(marker in message for marker in transient_markers):
                time.sleep(0.2 * (attempt + 1))
                continue
            return False
    normalized = str(text or '').strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if lowered in {'not found', 'could not read text'}:
        return False
    if 'failed to retrieve' in lowered or 'status code 404' in lowered:
        return False

    return True


def _chapter_max_verse_for_existing_chapter(bible, bible_lib_book, chapter):
    max_probe = 300
    low = 1
    high = 2

    while high <= max_probe and _chapter_has_verse(bible, bible_lib_book, chapter, high):
        low = high
        high *= 2

    high = min(high, max_probe)
    if _chapter_has_verse(bible, bible_lib_book, chapter, high):
        max_verse = high
    else:
        left = low + 1
        right = high - 1
        max_verse = low
        while left <= right:
            middle = (left + right) // 2
            if _chapter_has_verse(bible, bible_lib_book, chapter, middle):
                max_verse = middle
                left = middle + 1
            else:
                right = middle - 1

    return max_verse


def _build_chapter_index_for_bible(bible, only_books=None):
    requested_books = set(only_books or [])
    bible_index = {}
    for book_name in _VALID_BOOK_NAMES:
        if requested_books and book_name not in requested_books:
            continue
        bible_lib_book = BibleLibBibleBooks[book_name]
        chapter_map = {}
        chapter_count = _CANONICAL_CHAPTER_COUNTS.get(book_name, 0)
        for chapter in range(1, chapter_count + 1):
            max_verse = _chapter_max_verse_for_existing_chapter(bible, bible_lib_book, chapter)
            chapter_map[str(chapter)] = int(max_verse)
        if chapter_map:
            bible_index[book_name] = chapter_map
    return bible_index


def build_bible_study_chapter_index_for_bibles(bibles, only_books=None):
    with _CHAPTER_INDEX_LOCK:
        index_payload = _load_chapter_index()
        for bible in bibles:
            bible_id = str(getattr(bible, 'id', '') or '')
            if not bible_id:
                continue
            logger.info('Building Bible Study chapter index for bible %s', bible_id)
            existing = index_payload.get(bible_id)
            if not isinstance(existing, dict):
                existing = {}
            built = _build_chapter_index_for_bible(bible, only_books=only_books)
            existing.update(built)
            index_payload[bible_id] = existing
        _save_chapter_index(index_payload)


def _chapter_max_verse_for_bible(bible, book_name, chapter):
    bible_id = str(getattr(bible, 'id', '') or '')
    chapter_key = str(int(chapter))
    primary_id = _primary_chapter_index_bible_id()
    with _CHAPTER_INDEX_LOCK:
        index_payload = _load_chapter_index()
        bible_index = index_payload.get(bible_id)

        if not isinstance(bible_index, dict) and _chapter_index_autobuild_enabled():
            logger.info('Building Bible Study chapter index for bible %s', bible_id)
            bible_index = _build_chapter_index_for_bible(bible)
            index_payload[bible_id] = bible_index
            _save_chapter_index(index_payload)

        if not isinstance(bible_index, dict):
            bible_index = {}

        for candidate_id in [bible_id, primary_id]:
            if not candidate_id:
                continue
            candidate_index = index_payload.get(candidate_id)
            if not isinstance(candidate_index, dict):
                continue
            book_index = candidate_index.get(book_name)
            if not isinstance(book_index, dict):
                continue
            max_verse = book_index.get(chapter_key)
            if isinstance(max_verse, int) and 0 <= max_verse <= 176:
                return max_verse

        if not _chapter_index_live_fetch_enabled():
            return 0

        if isinstance(bible_index, dict):
            bible_lib_book = BibleLibBibleBooks[book_name]
            if not _chapter_has_verse(bible, bible_lib_book, int(chapter_key), 1):
                max_verse = 0
            else:
                max_verse = _chapter_max_verse_for_existing_chapter(bible, bible_lib_book, int(chapter_key))
            if book_name not in bible_index or not isinstance(bible_index.get(book_name), dict):
                bible_index[book_name] = {}
            bible_index[book_name][chapter_key] = int(max_verse)
            index_payload[bible_id] = bible_index
            _save_chapter_index(index_payload)
            return int(max_verse)

    return 0


def _default_bible_ids_from_settings(enabled_bibles, max_bibles):
    configured = getattr(settings, 'BIBLE_STUDY_DEFAULT_BIBLE_IDS_BY_LANGUAGE', {}) or {}
    if not isinstance(configured, dict):
        return []

    visible_by_id = {str(bible.id): bible for bible in enabled_bibles}
    selected_ids = []

    for language_code, configured_ids in configured.items():
        normalized_language = str(language_code or '').strip().upper()[:2]
        if isinstance(configured_ids, (str, int)):
            configured_list = [configured_ids]
        else:
            configured_list = list(configured_ids or [])

        for bible_id in configured_list:
            normalized_id = str(bible_id or '').strip()
            bible = visible_by_id.get(normalized_id)
            if not bible:
                continue
            bible_language = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
            if normalized_language and bible_language != normalized_language:
                continue
            if normalized_id not in selected_ids:
                selected_ids.append(normalized_id)
            break

        if len(selected_ids) >= max_bibles:
            break

    return selected_ids[:max_bibles]


class BibleStudyView(View):
    def get(self, request):
        max_verses = int(getattr(settings, 'BIBLE_STUDY_MAX_VERSES', 5))
        show_original_text = str(request.GET.get('show_original', '')).strip().lower() in {'1', 'true', 'yes', 'on'}
        max_bibles = 4

        bible_books = [(b.name, str(b.value)) for b in BibleBooks]

        all_bibles = BibleTranslation().all_in_supported_languages()
        enabled_bibles = sorted(
            filter_visible_bibles_for_request(request, all_bibles),
            key=_bible_dropdown_sort_key,
        )

        book = request.GET.get('book', 'JohnFirstBook')
        if book not in _VALID_BOOK_NAMES:
            book = 'JohnFirstBook'

        chapter = _safe_int(request.GET.get('chapter'), 2)
        start_verse = _safe_int(request.GET.get('start_verse'), 3)
        end_verse = _safe_int(request.GET.get('end_verse'), 6)
        end_verse = max(start_verse, end_verse)
        end_verse = min(end_verse, start_verse + max_verses - 1)

        bible_ids = request.GET.getlist('bible_id')
        if not bible_ids:
            bible_ids = _default_bible_ids_from_settings(enabled_bibles, max_bibles)
        if not bible_ids:
            default_bible = UserPreferences(request.session).bible
            bible_ids = [default_bible.id] if default_bible else []
        bible_ids = [str(bid).strip() for bid in bible_ids if str(bid).strip()][:max_bibles]

        visible_ids = {b.id for b in enabled_bibles}
        bible_ids = [bid for bid in bible_ids if bid in visible_ids]
        if not bible_ids and enabled_bibles:
            bible_ids = [enabled_bibles[0].id]

        verse_range = list(range(start_verse, end_verse + 1))
        is_ot_book = book in _OT_BOOKS
        sefaria_book = _SEFARIA_BOOK_NAMES.get(book, book)
        scriptura_book = _SCRIPTURA_BOOK_NAMES.get(book, book)

        verse_data = []
        verse_texts_by_bible = {}
        for v in verse_range:
            verse_data.append({
                'verse_num': v,
                'sefaria_ref': f'{sefaria_book} {chapter}:{v}' if is_ot_book else '',
                'scriptura_book': scriptura_book,
                'scriptura_chapter': chapter,
                'scriptura_verse': v,
                'is_ot': is_ot_book,
            })

        bt = BibleTranslation()
        selected_bibles = []
        for bid in bible_ids:
            bible_obj = bt.get(bid)
            if bible_obj:
                bible_book = BibleLibBibleBooks[book]
                verse_texts = {}
                verse_sources = {}
                for v in verse_range:
                    cache_key = f'bible_study:v1:{bid}:{book}:{chapter}:{v}'
                    cached = None if getattr(settings, 'DISABLE_CACHE_FOR_DEBUG', False) else cache.get(cache_key)
                    if cached is not None:
                        verse_texts[str(v)] = cached
                        verse_sources[str(v)] = 'cache'
                        continue
                    try:
                        text = bible_obj.verses(bible_book, chapter, v, chapter, v)
                    except Exception:
                        logger.exception('Failed to load verse text for bible=%s book=%s chapter=%s verse=%s', bid, book, chapter, v)
                        text = ''
                    verse_texts[str(v)] = text or ''
                    verse_sources[str(v)] = 'api'
                    if text:
                        cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)

                _record_bible_usage_for_sources(
                    request=request,
                    bible=bible_obj,
                    verse_sources=verse_sources,
                    endpoint=BibleTranslationUsageDaily.ENDPOINT_STUDY_PAGE,
                )

                verse_texts_by_bible[bid] = verse_texts
                selected_bibles.append({
                    'id': bid,
                    'name': bible_obj.name,
                    'language_code': str(getattr(bible_obj, 'language', '') or '').strip().upper()[:2],
                    'display_name': f"{str(getattr(bible_obj, 'language', '') or '').strip().upper()[:2]} - {bible_obj.name}" if str(getattr(bible_obj, 'language', '') or '').strip() else bible_obj.name,
                    'verse_texts': verse_texts,
                    'verse_sources': verse_sources,
                    'copyright': getattr(bible_obj, 'copyright', ''),
                })

        book_label = str(BibleBooks[book].value) if book in _VALID_BOOK_NAMES else book
        visible_bible_slots = max(1, min(max_bibles, len(selected_bibles) or 1))

        return render(request, 'bible_study/bible_study.html', {
            'bible_books': bible_books,
            'enabled_bibles': enabled_bibles,
            'selected_book': book,
            'selected_book_label': book_label,
            'selected_chapter': chapter,
            'selected_start_verse': start_verse,
            'selected_end_verse': end_verse,
            'selected_bible_ids': bible_ids,
            'selected_bibles': selected_bibles,
            'verse_data': verse_data,
            'max_verses': max_verses,
            'max_bibles': max_bibles,
            'visible_bible_slots': visible_bible_slots,
            'is_ot_book': is_ot_book,
            'show_original_text': show_original_text,
        })


class BibleStudyVersesView(View):
    """AJAX endpoint: returns verse texts for a given bible + book/chapter/verse range."""

    def post(self, request):
        bible_id = str(request.POST.get('bible_id', '')).strip()
        book_name = str(request.POST.get('book', '')).strip()
        chapter = _safe_int(request.POST.get('chapter'), 1)
        start_verse = _safe_int(request.POST.get('start_verse'), 1)
        end_verse = _safe_int(request.POST.get('end_verse'), start_verse)
        end_verse = max(start_verse, end_verse)

        max_verses = int(getattr(settings, 'BIBLE_STUDY_MAX_VERSES', 5))
        end_verse = min(end_verse, start_verse + max_verses - 1)

        if book_name not in _VALID_BOOK_NAMES:
            return JsonResponse({'error': 'Invalid book'}, status=400)

        if not is_bible_id_visible_for_request(request, bible_id):
            return JsonResponse({'error': 'Bible not available'}, status=403)

        bt = BibleTranslation()
        bible = bt.get(bible_id)
        if not bible:
            return JsonResponse({'error': 'Bible not found'}, status=404)

        bible_lib_book = BibleLibBibleBooks[book_name]
        disable_cache = getattr(settings, 'DISABLE_CACHE_FOR_DEBUG', False)
        verses = {}
        verse_sources = {}
        for v in range(start_verse, end_verse + 1):
            cache_key = f'bible_study:v1:{bible_id}:{book_name}:{chapter}:{v}'
            cached = None if disable_cache else cache.get(cache_key)
            if cached is not None:
                verses[str(v)] = cached
                verse_sources[str(v)] = 'cache'
                continue
            try:
                text = bible.verses(bible_lib_book, chapter, v, chapter, v)
            except Exception:
                text = ''
            verses[str(v)] = text or ''
            verse_sources[str(v)] = 'api'
            if text:
                cache.set(cache_key, text, VERSE_CACHE_TIMEOUT)

        _record_bible_usage_for_sources(
            request=request,
            bible=bible,
            verse_sources=verse_sources,
            endpoint=BibleTranslationUsageDaily.ENDPOINT_VERSES_API,
        )

        language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
        display_name = f'{language_code} - {getattr(bible, "name", bible_id)}' if language_code else getattr(bible, 'name', bible_id)
        return JsonResponse({
            'verses': verses,
            'verse_sources': verse_sources,
            'bible_name': getattr(bible, 'name', bible_id),
            'bible_display_name': display_name,
            'copyright': getattr(bible, 'copyright', ''),
        })


class BibleStudySearchView(View):
    """AJAX endpoint: proxies API.Bible search for the first selected translation."""

    def get(self, request):
        bible_id = str(request.GET.get('bible_id', '')).strip()
        query = str(request.GET.get('query', '')).strip()
        limit = _safe_search_limit(request.GET.get('limit'))
        offset = _safe_search_offset(request.GET.get('offset'))
        sort = _safe_search_sort(request.GET.get('sort'))
        fuzziness = _safe_search_fuzziness(request.GET.get('fuzziness'))
        search_range = _safe_search_range(request.GET.get('range'))

        if not query:
            return JsonResponse({'error': 'Enter words to search for.'}, status=400)
        if len(query) > 120:
            return JsonResponse({'error': 'Search text is too long.'}, status=400)

        if not is_bible_id_visible_for_request(request, bible_id):
            return JsonResponse({'error': 'Bible not available'}, status=403)

        bible = BibleTranslation().get(bible_id)
        if not bible:
            return JsonResponse({'error': 'Bible not found'}, status=404)

        try:
            api_payload = _api_bible_search_payload(bible_id, query, limit, offset, sort, fuzziness, search_range)
        except Exception:
            logger.exception('Bible Study API.Bible search failed for bible=%s query=%s', bible_id, query)
            return JsonResponse({'error': 'Search is not available for this translation right now.'}, status=502)

        data = api_payload.get('data', {}) if isinstance(api_payload, dict) else {}
        verses = data.get('verses', []) if isinstance(data, dict) else []
        results = []
        for verse in verses[:limit]:
            if not isinstance(verse, dict):
                continue
            results.append({
                'id': verse.get('id', ''),
                'reference': verse.get('reference', ''),
                'text': verse.get('text', ''),
            })

        total = int(data.get('total', len(results)) or len(results)) if isinstance(data, dict) else len(results)
        verse_count = int(data.get('verseCount', total) or total) if isinstance(data, dict) else total
        page = (offset // limit) + 1
        page_count = max(1, ((total + limit - 1) // limit) if total else 1)
        page_summary_count = min(page_count, int(getattr(settings, 'BIBLE_STUDY_SEARCH_PAGE_SUMMARY_LIMIT', 12)))
        pages = []
        for page_number in range(1, page_summary_count + 1):
            page_offset = (page_number - 1) * limit
            page_verses = verses if page_offset == offset else []
            if page_offset != offset:
                try:
                    summary_payload = _api_bible_search_payload(bible_id, query, limit, page_offset, sort, fuzziness, search_range)
                    summary_data = summary_payload.get('data', {}) if isinstance(summary_payload, dict) else {}
                    page_verses = summary_data.get('verses', []) if isinstance(summary_data, dict) else []
                except Exception:
                    page_verses = []
            pages.append({
                'page': page_number,
                'offset': page_offset,
                'range_label': _search_result_reference_span(page_verses),
                'current': page_number == page,
            })

        language_code = str(getattr(bible, 'language', '') or '').strip().upper()[:2]
        display_name = f'{language_code} - {getattr(bible, "name", bible_id)}' if language_code else getattr(bible, 'name', bible_id)
        return JsonResponse({
            'query': query,
            'bible_id': bible_id,
            'bible_display_name': display_name,
            'limit': limit,
            'offset': offset,
            'sort': sort,
            'fuzziness': fuzziness,
            'range': search_range,
            'total': total,
            'verse_count': verse_count,
            'page': page,
            'page_count': page_count,
            'pages': pages,
            'results': results,
        })


class BibleStudyChapterMetaView(View):
    """AJAX endpoint: returns the max verse number available for a chapter."""

    def get(self, request):
        book_name = str(request.GET.get('book', '')).strip()
        chapter = _safe_int(request.GET.get('chapter'), 1)
        bible_id = str(request.GET.get('bible_id', '')).strip()

        if book_name not in _VALID_BOOK_NAMES:
            return JsonResponse({'error': 'Invalid book'}, status=400)

        all_bibles = BibleTranslation().all_in_supported_languages()
        enabled_bibles = filter_visible_bibles_for_request(request, all_bibles)

        if bible_id:
            if not is_bible_id_visible_for_request(request, bible_id):
                return JsonResponse({'error': 'Bible not available'}, status=403)
            bible = BibleTranslation().get(bible_id)
        else:
            default_bible = UserPreferences(request.session).bible
            default_id = getattr(default_bible, 'id', '') if default_bible else ''
            visible_by_id = {b.id: b for b in enabled_bibles}
            bible = visible_by_id.get(default_id)
            if not bible and enabled_bibles:
                bible = enabled_bibles[0]

        if not bible:
            return JsonResponse({'error': 'Bible not found'}, status=404)

        max_verse = _chapter_max_verse_for_bible(bible, book_name, chapter)
        return JsonResponse({
            'book': book_name,
            'chapter': chapter,
            'bible_id': getattr(bible, 'id', ''),
            'max_verse': max_verse,
        })


class BibleStudyOriginalTextView(View):
    """AJAX endpoint: returns original-language verses with candidate Strongs lookups."""

    def post(self, request):
        book_name = str(request.POST.get('book', '')).strip()
        chapter = _safe_int(request.POST.get('chapter'), 1)
        start_verse = _safe_int(request.POST.get('start_verse'), 1)
        end_verse = _safe_int(request.POST.get('end_verse'), start_verse)
        end_verse = max(start_verse, end_verse)

        max_verses = int(getattr(settings, 'BIBLE_STUDY_MAX_VERSES', 5))
        end_verse = min(end_verse, start_verse + max_verses - 1)

        if book_name not in _VALID_BOOK_NAMES:
            return JsonResponse({'error': 'Invalid book'}, status=400)

        verses = {}
        for verse in range(start_verse, end_verse + 1):
            verses[str(verse)] = original_text_payload(book_name, chapter, verse)

        return JsonResponse({'verses': verses})
