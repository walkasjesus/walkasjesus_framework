import html
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.core.cache import cache

from walkasjesus_app.models import BibleTranslation


ORIGINAL_GREEK_BIBLE_ID = '7644de2e4c5188e5-01'
ORIGINAL_HEBREW_BIBLE_ID = '2c500771ea16da93-01'
ORIGINAL_TEXT_CACHE_TIMEOUT = 60 * 60 * 24 * 30

_OT_BOOKS = {
    'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy', 'Joshua', 'Judges', 'Ruth',
    'SamuelFirstBook', 'SamuelSecondBook', 'KingsFirstBook', 'KingsSecondBook',
    'ChroniclesFirstBook', 'ChroniclesSecondBook', 'Ezra', 'Nehemiah', 'Esther', 'Job',
    'Psalms', 'Proverbs', 'Ecclesiastes', 'SongOfSolomon', 'Isaiah', 'Jeremiah',
    'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel', 'Amos', 'Obadiah', 'Jonah',
    'Micah', 'Nahum', 'Habakkuk', 'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
}

_WORD_RE = re.compile(r"[\u0370-\u03FF\u1F00-\u1FFF\u0590-\u05FF\uFB1D-\uFB4F']+|[^\s]", re.UNICODE)
_STEP_CODE_RE = re.compile(r'[GH]\d+(?:_[A-Za-z]+|[A-Za-z]+)?')

_STEPBIBLE_OT_FILES = {
    'Genesis': 'TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Exodus': 'TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Leviticus': 'TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Numbers': 'TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Deuteronomy': 'TAHOT Gen-Deu - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Joshua': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Judges': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Ruth': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'SamuelFirstBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'SamuelSecondBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'KingsFirstBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'KingsSecondBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'ChroniclesFirstBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'ChroniclesSecondBook': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Ezra': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Nehemiah': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Esther': 'TAHOT Jos-Est - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Job': 'TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Psalms': 'TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Proverbs': 'TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Ecclesiastes': 'TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'SongOfSolomon': 'TAHOT Job-Sng - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Isaiah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Jeremiah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Lamentations': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Ezekiel': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Daniel': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Hosea': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Joel': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Amos': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Obadiah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Jonah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Micah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Nahum': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Habakkuk': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Zephaniah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Haggai': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Zechariah': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
    'Malachi': 'TAHOT Isa-Mal - Translators Amalgamated Hebrew OT - STEPBible.org CC BY.txt',
}

_STEPBIBLE_NT_FILES = {
    'Matthew': 'TAGNT Mat-Jhn - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Mark': 'TAGNT Mat-Jhn - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Luke': 'TAGNT Mat-Jhn - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'John': 'TAGNT Mat-Jhn - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Acts': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Romans': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'CorinthiansFirstBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'CorinthiansSecondBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Galatians': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Ephesians': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Philippians': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Colossians': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'ThessaloniansFirstBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'ThessaloniansSecondBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'TimothyFirstBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'TimothySecondBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Titus': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Philemon': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Hebrews': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'James': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'PeterFirstBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'PeterSecondBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'JohnFirstBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'JohnSecondBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'JohnThirdBook': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Jude': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
    'Revelation': 'TAGNT Act-Rev - Translators Amalgamated Greek NT - STEPBible.org CC-BY.txt',
}


def is_ot_book(book_name):
    return str(book_name or '') in _OT_BOOKS


def original_language_code(book_name):
    return 'hebrew' if is_ot_book(book_name) else 'greek'


def original_bible_id(book_name):
    return ORIGINAL_HEBREW_BIBLE_ID if is_ot_book(book_name) else ORIGINAL_GREEK_BIBLE_ID


def _stepbible_root():
    return Path(__file__).resolve().parents[2] / 'data' / 'stepbible'


def _open_scriptures_root():
    return Path(__file__).resolve().parents[2] / 'data' / 'strongs'


def _load_js_dictionary(path, variable_name):
    raw_text = path.read_text(encoding='utf-8')
    prefix = f'var {variable_name} = '
    start = raw_text.find(prefix)
    if start == -1:
        raise ValueError(f'Could not find {variable_name} in {path}')
    object_start = raw_text.find('{', start + len(prefix))
    if object_start == -1:
        raise ValueError(f'Could not find object start for {variable_name} in {path}')

    depth = 0
    in_string = False
    escaped = False
    object_end = -1
    for index in range(object_start, len(raw_text)):
        ch = raw_text[index]
        if in_string:
            if escaped:
                escaped = False
            elif ch == '\\':
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == '{':
            depth += 1
            continue
        if ch == '}':
            depth -= 1
            if depth == 0:
                object_end = index
                break

    if object_end == -1:
        raise ValueError(f'Could not find object end for {variable_name} in {path}')

    return json.loads(raw_text[object_start:object_end + 1])


def _strip_marks(value):
    normalized = unicodedata.normalize('NFD', str(value or ''))
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def _strip_html(value):
    normalized = html.unescape(str(value or ''))
    normalized = re.sub(r'<[^>]+>', ' ', normalized)
    normalized = normalized.replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', normalized).strip()


def _normalize_lookup_word(value, language):
    value = str(value or '').strip()
    if not value:
        return ''

    allowed = []
    for ch in value:
        category = unicodedata.category(ch)
        if category.startswith('L') or category.startswith('M') or ch in {"'", '׳', '״'}:
            allowed.append(ch)
    compact = ''.join(allowed)
    if language == 'greek':
        compact = _strip_marks(compact).lower()
    else:
        compact = _strip_marks(compact)
        compact = compact.replace('׳', '').replace('״', '')
    return compact


def _glosses_from_text(raw):
    raw = str(raw or '').strip()
    if not raw:
        return []
    parts = [part.strip(' .;') for part in raw.split(',') if part.strip(' .;')]
    return parts[:12]


def _meaning_list(*values):
    ordered = []
    seen = set()
    for raw in values:
        text = str(raw or '').strip()
        if not text:
            continue
        normalized = text.replace(';', ',').replace('/', ',')
        for part in normalized.split(','):
            item = part.strip(' .;')
            if not item:
                continue
            if item.startswith('X '):
                item = item[2:].strip()
            item = item.replace('(', '').replace(')', '')
            item = re.sub(r'\s+', ' ', item).strip(' .;')
            if not item:
                continue
            lower_item = item.lower()
            if lower_item in seen:
                continue
            seen.add(lower_item)
            ordered.append(item)
    return ordered[:20]


def _extract_refs_from_html(raw_html):
    text = _strip_html(raw_html)
    refs = []
    seen = set()
    for match in re.findall(r'\b(?:[1-3]?[A-Z][a-z]{1,3})\.\d+:\d+(?:[-,]\d+)?\b', text):
        if match in seen:
            continue
        seen.add(match)
        refs.append(match)
    return refs[:40]


def _normalize_step_code(raw_code):
    code = str(raw_code or '').strip().strip('{}[]()')
    if not code:
        return ''
    return code.replace('=', '').strip()


def _extract_step_codes(value):
    ordered = []
    seen = set()
    for match in _STEP_CODE_RE.findall(str(value or '')):
        normalized = _normalize_step_code(match)
        if normalized and normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def _stepbible_book_code(book_name):
    code = BibleLibBibleBooks.abbreviation(BibleLibBibleBooks[book_name])
    if code[:1].isdigit():
        return code[:2] + code[2:].lower()
    return code[:1] + code[1:].lower()


def _stepbible_file_for_book(book_name):
    filename = _STEPBIBLE_OT_FILES.get(book_name) if is_ot_book(book_name) else _STEPBIBLE_NT_FILES.get(book_name)
    if not filename:
        raise KeyError(f'No STEPBible file mapped for {book_name}')
    return _stepbible_root() / 'Translators Amalgamated OT+NT' / filename


def _parse_token_with_transliteration(value):
    raw = str(value or '').strip()
    match = re.match(r'^(.*?)\s*\((.*?)\)\s*$', raw)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return raw, ''


def _clean_hebrew_surface(value):
    cleaned = str(value or '').replace('/', '').replace('\\', '').strip()
    return re.sub(r'\s+', ' ', cleaned)


def _clean_translation_label(value):
    normalized = str(value or '').replace('/', ' ').strip()
    normalized = normalized.replace('<', '[').replace('>', ']')
    return re.sub(r'\s+', ' ', normalized)


@lru_cache(maxsize=2)
def _stepbible_lexicon(language):
    base = _stepbible_root() / 'Lexicons'
    path = base / (
        'TBESH - Translators Brief lexicon of Extended Strongs for Hebrew - STEPBible.org CC BY.txt'
        if language == 'hebrew'
        else 'TBESG - Translators Brief lexicon of Extended Strongs for Greek - STEPBible.org CC BY.txt'
    )
    exact = {}
    with path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.rstrip('\n')
            if not line or not line[:1] in {'G', 'H'}:
                continue
            columns = line.split('\t')
            if len(columns) < 8:
                continue
            display_code = _normalize_step_code(columns[2] or columns[0])
            if not display_code:
                continue
            exact[display_code] = {
                'strongs_number': display_code,
                'lemma': str(columns[3] or '').strip(),
                'transliteration': str(columns[4] or '').strip(),
                'grammar': str(columns[5] or '').strip(),
                'short_gloss': _clean_translation_label(columns[6] or ''),
                'definition': _strip_html(columns[7] if len(columns) > 7 else ''),
                'full_entry': str(columns[7] if len(columns) > 7 else ''),
                'references': _extract_refs_from_html(columns[7] if len(columns) > 7 else ''),
            }
    return exact


@lru_cache(maxsize=2)
def _open_scriptures_dictionary(language):
    base = _open_scriptures_root()
    if language == 'greek':
                return _load_js_dictionary(base / 'greek' / 'strongs-greek-dictionary.js', 'strongsGreekDictionary')
    return _load_js_dictionary(base / 'hebrew' / 'strongs-hebrew-dictionary.js', 'strongsHebrewDictionary')


def _lookup_open_scriptures_entry(code, language):
    normalized = _normalize_step_code(code)
    if not normalized:
        return None

    dictionary = _open_scriptures_dictionary(language)
    if normalized in dictionary:
        return dictionary[normalized]

    base = re.sub(r'([A-Za-z_]+)$', '', normalized)
    return dictionary.get(base) if base else None


def _lookup_step_lexicon_entry(code, language):
    normalized = _normalize_step_code(code)
    if not normalized:
        return None

    lexicon = _stepbible_lexicon(language)
    if normalized in lexicon:
        return lexicon[normalized]

    if '_' in normalized:
        base = normalized.split('_', 1)[0]
        if base in lexicon:
            return lexicon[base]

    base = re.sub(r'([A-Za-z]+)$', '', normalized)
    if base in lexicon:
        return lexicon[base]

    return None


def _candidate_payload(strongs_number, language, row_data, primary=False):
    lexicon_entry = _lookup_step_lexicon_entry(strongs_number, language) or {}
    os_entry = _lookup_open_scriptures_entry(strongs_number, language) or {}
    base_code = re.search(r'[GH]\d+', str(strongs_number or ''))
    normalized_code = base_code.group(0) if base_code else str(strongs_number or '')
    lemma = str((row_data.get('lemma') if primary else '') or lexicon_entry.get('lemma') or '')
    transliteration = str((row_data.get('transliteration') if primary else '') or lexicon_entry.get('transliteration') or os_entry.get('translit') or os_entry.get('xlit') or '')
    short_gloss = str((row_data.get('translation_label') if primary else '') or lexicon_entry.get('short_gloss') or '')
    definition = str(os_entry.get('strongs_def') or (row_data.get('definition') if primary else '') or lexicon_entry.get('definition') or short_gloss)
    kjv_definition = str(os_entry.get('kjv_def') or short_gloss)
    possible_translations = _meaning_list(short_gloss, kjv_definition, lexicon_entry.get('short_gloss') or '')
    return {
        'strongs_number': normalized_code,
        'language': 'Hebrew' if language == 'hebrew' else 'Greek',
        'lemma': lemma,
        'transliteration': transliteration,
        'pronunciation': str(os_entry.get('pron') or ''),
        'definition': definition,
        'kjv_definition': kjv_definition,
        'derivation': str(os_entry.get('derivation') or ''),
        'glosses': possible_translations[:12],
        'possible_translations': possible_translations,
        'grammar': str(row_data.get('grammar') or lexicon_entry.get('grammar') or ''),
        'references': list(lexicon_entry.get('references') or []),
        'lexicon_summary': _strip_html(lexicon_entry.get('full_entry') or ''),
        'blueletter_url': 'https://www.blueletterbible.org/lexicon/{}/kjv/{}/0-1/'.format(
            normalized_code.lower(),
            'wlc' if language == 'hebrew' else 'tr',
        ),
    }


def _primary_translation_label(candidates):
    if not candidates:
        return ''

    primary = candidates[0]
    glosses = list(primary.get('glosses') or [])
    if glosses:
        return str(glosses[0])

    kjv_definition = str(primary.get('kjv_definition') or '').strip()
    if kjv_definition:
        first = re.split(r'[;,/]', kjv_definition)[0].strip(' .')
        if first:
            return first

    definition = str(primary.get('definition') or '').strip()
    if definition:
        first = re.split(r'[;,/]', definition)[0].strip(' .')
        if first:
            return first

    return ''


def _stepbible_rows_for_verse(book_name, chapter, verse):
    reference_prefix = f'{_stepbible_book_code(book_name)}.{chapter}.{verse}#'
    rows = []
    path = _stepbible_file_for_book(book_name)
    with path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.rstrip('\n')
            if not line.startswith(reference_prefix):
                continue
            rows.append(line)
    return rows


def _parse_stepbible_row(line, language):
    columns = line.split('\t')
    if language == 'greek':
        surface_text, transliteration = _parse_token_with_transliteration(columns[1] if len(columns) > 1 else '')
        dstrong_grammar = str(columns[3] if len(columns) > 3 else '')
        lemma_gloss = str(columns[4] if len(columns) > 4 else '')
        lemma, _, gloss = lemma_gloss.partition('=')
        translation_label = _clean_translation_label(columns[9] if len(columns) > 9 and columns[9] else (columns[2] if len(columns) > 2 else gloss))
        grammar = dstrong_grammar.split('=', 1)[1].strip() if '=' in dstrong_grammar else ''
        strongs_numbers = []
        for source in [columns[11] if len(columns) > 11 else '', dstrong_grammar, columns[12] if len(columns) > 12 else '']:
            for code in _extract_step_codes(source):
                if code not in strongs_numbers:
                    strongs_numbers.append(code)
        return {
            'surface_text': surface_text,
            'sentence_text': surface_text,
            'transliteration': transliteration,
            'translation_label': translation_label,
            'lemma': str(lemma or '').strip(),
            'definition': _clean_translation_label(gloss),
            'grammar': grammar,
            'strongs_numbers': strongs_numbers,
        }

    surface_text = _clean_hebrew_surface(columns[1] if len(columns) > 1 else '')
    translation_label = _clean_translation_label(columns[3] if len(columns) > 3 else '')
    strongs_numbers = []
    for source in [columns[8] if len(columns) > 8 else '', columns[4] if len(columns) > 4 else '', columns[9] if len(columns) > 9 else '', columns[11] if len(columns) > 11 else '']:
        for code in _extract_step_codes(source):
            if code not in strongs_numbers:
                strongs_numbers.append(code)
    return {
        'surface_text': surface_text,
        'sentence_text': surface_text,
        'transliteration': str(columns[2] if len(columns) > 2 else '').strip(),
        'translation_label': translation_label,
        'lemma': '',
        'definition': translation_label,
        'grammar': str(columns[5] if len(columns) > 5 else '').strip(),
        'strongs_numbers': strongs_numbers,
    }


def _fallback_token_payload(raw_token, language):
    lookup_key = _normalize_lookup_word(raw_token, language)

    return {
        'text': raw_token,
        'sentence_text': raw_token,
        'lookup_key': lookup_key,
        'clickable': False,
        'has_candidates': False,
        'strongs_count': 0,
        'translation_label': '',
        'detail_note': '',
        'hover_summary': '',
        'candidates': [],
        'grammar': '',
        'tagging_source': '',
    }


def _token_payload_from_step_row(row_data, language):
    lookup_key = _normalize_lookup_word(row_data.get('surface_text') or '', language)
    candidates = []
    for index, strongs_number in enumerate(row_data.get('strongs_numbers') or []):
        candidates.append(_candidate_payload(strongs_number, language, row_data, primary=index == 0))

    primary = candidates[0] if candidates else None
    hover_lines = []
    if primary:
        hover_lines.append(primary['strongs_number'])
        if primary['lemma']:
            hover_lines.append(primary['lemma'])
        gloss_text = ', '.join(primary['glosses'][:4]) or primary['definition']
        if gloss_text:
            hover_lines.append(gloss_text)

    return {
        'text': str(row_data.get('surface_text') or ''),
        'sentence_text': str(row_data.get('sentence_text') or row_data.get('surface_text') or ''),
        'lookup_key': lookup_key,
        'clickable': bool(lookup_key),
        'has_candidates': bool(candidates),
        'strongs_count': len(candidates),
        'translation_label': str(row_data.get('translation_label') or _primary_translation_label(candidates) or ''),
        'detail_note': '' if candidates else 'This word is aligned in STEPBible, but no lexicon entry was resolved from its Strong\'s tag.',
        'hover_summary': ' | '.join(hover_lines),
        'candidates': candidates,
        'grammar': str(row_data.get('grammar') or ''),
        'tagging_source': 'STEPBible',
    }


def original_text_payload(book_name, chapter, verse):
    cache_key = f'bible_study:original:v4:{book_name}:{chapter}:{verse}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    language = original_language_code(book_name)
    bible = BibleTranslation().get(original_bible_id(book_name))
    original_text = bible.verses(BibleLibBibleBooks[book_name], chapter, verse, chapter, verse) or ''
    step_rows = [_parse_stepbible_row(row, language) for row in _stepbible_rows_for_verse(book_name, chapter, verse)]
    words = [_token_payload_from_step_row(row, language) for row in step_rows if row and str(row.get('surface_text') or '').strip()]
    if not words:
        raw_tokens = _WORD_RE.findall(original_text)
        words = [_fallback_token_payload(token, language) for token in raw_tokens if str(token or '').strip()]

    sentence = ' '.join(str(word.get('sentence_text') or word.get('text') or '').strip() for word in words if str(word.get('sentence_text') or word.get('text') or '').strip()) or original_text
    first_clickable = next((word for word in words if word['clickable']), None)

    payload = {
        'book': book_name,
        'chapter': int(chapter),
        'verse': int(verse),
        'language_code': 'hbo' if language == 'hebrew' else 'grc',
        'language_label': 'Hebrew' if language == 'hebrew' else 'Greek',
        'source_bible_id': original_bible_id(book_name),
        'source_bible_name': getattr(bible, 'name', ''),
        'sentence': sentence,
        'tagging_source_name': 'STEPBible TAGNT' if language == 'greek' else 'STEPBible TAHOT',
        'tagging_source_license': 'CC BY 4.0',
        'words': words,
        'selected_word': first_clickable,
    }
    cache.set(cache_key, payload, ORIGINAL_TEXT_CACHE_TIMEOUT)
    return payload