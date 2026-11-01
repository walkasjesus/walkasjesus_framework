import copy
import gzip
import hashlib
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


def _lxx_index_path():
    return Path(__file__).resolve().parents[2] / 'data' / 'lxx_greek_to_hebrew.json'


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


@lru_cache(maxsize=1)
def _lxx_greek_to_hebrew_index():
    path = _lxx_index_path()
    if not path.exists():
        return {}
    try:
        with path.open('r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _strip_marks(value):
    normalized = unicodedata.normalize('NFD', str(value or ''))
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def _strip_html(value):
    normalized = html.unescape(str(value or ''))
    normalized = re.sub(r'<[^>]+>', ' ', normalized)
    normalized = normalized.replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', normalized).strip()


def _expand_reference_blob(reference):
    raw = re.sub(r'\s+', ' ', str(reference or '').strip())
    if not raw:
        return []

    if re.match(r'^[1-3]?[A-Za-z]{1,4}\s+\d+$', raw):
        book_code, verse = raw.split()
        return [f'{book_code}.1:{verse}']

    parts = []
    active_book = ''
    active_chapter = ''
    for token in re.split(r'[;,]\s*|\s+', raw):
        token = token.strip()
        if not token:
            continue

        full_match = re.match(r'^([1-3]?[A-Za-z]{1,4})\.(\d+):(\d+(?:-\d+)?)$', token)
        if full_match:
            active_book = full_match.group(1)
            active_chapter = full_match.group(2)
            parts.append(f'{active_book}.{active_chapter}:{full_match.group(3)}')
            continue

        chapter_match = re.match(r'^(\d+):(\d+(?:-\d+)?)$', token)
        if chapter_match and active_book:
            active_chapter = chapter_match.group(1)
            parts.append(f'{active_book}.{active_chapter}:{chapter_match.group(2)}')
            continue

        verse_match = re.match(r'^(\d+(?:-\d+)?)$', token)
        if verse_match and active_book and active_chapter:
            parts.append(f'{active_book}.{active_chapter}:{verse_match.group(1)}')

    return _dedupe_preserve_order(parts)


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


def _parse_structured_definitions(full_entry_html):
    """Parse TBESG __N. numbered sense markers into a structured list of definitions.

    Each entry in the TBESG full_entry looks like:
      __1. <b>to watch over, guard, keep, preserve</b>: <ref='Mat.27.36'>Mat.27:36</ref>, ...
      __2. <b>to watch, give heed to, observe</b>: ...
    Returns a list of dicts with 'number', 'heading', 'summary', and 'references'.
    """
    raw = str(full_entry_html or '')
    if not raw:
        return []

    results = []
    # Split on numbered sense markers __1., __2., etc.
    parts = re.split(r'(?=__\d+\.)', raw)
    for part in parts:
        m = re.match(r'__(\d+)\.\s*(.*)', part, re.DOTALL)
        if not m:
            continue
        number = int(m.group(1))
        content = m.group(2).strip()

        # Extract the bold heading (primary sense definition)
        bold_match = re.search(r'<b>(.*?)</b>', content)
        heading = _strip_html(bold_match.group(1)) if bold_match else ''

        # Remove bold tag and synonym block <re>...</re> to get usage examples
        body = re.sub(r'<b>.*?</b>', '', content, count=1)
        body = re.sub(r'<re>.*?</re>', '', body, flags=re.DOTALL)

        # Extract scripture references: <ref='Mat.27.36'>Mat.27:36</ref>
        refs = []
        for ref_text in re.findall(r"<ref='[^']*'>([^<]+)</ref>", body):
            refs.extend(_expand_reference_blob(ref_text))
        refs = _dedupe_preserve_order(refs)

        # Clean body to plain text, strip leading colon/semicolon
        summary = _strip_html(body).strip()
        summary = re.sub(r'^\s*[;:]\s*', '', summary)
        summary = re.sub(r'\s+', ' ', summary).strip()

        if heading:
            results.append({
                'number': number,
                'heading': heading,
                'summary': summary,
                'references': refs[:20],
            })
    return results


def _clean_outline_label(value):
    text = _strip_html(value)
    text = re.sub(r'\s+', ' ', text).strip(' .;:')
    return text


def _grammar_label(value):
    grammar = str(value or '').strip()
    if not grammar:
        return ''

    if grammar.startswith('H:A'):
        return 'adjective'
    if grammar.startswith('H:V'):
        return 'verb'
    if grammar.startswith('H:N-M'):
        return 'masculine noun'
    if grammar.startswith('H:N-F'):
        return 'feminine noun'
    if grammar.startswith('H:N'):
        return 'noun'
    if grammar.startswith('G:V'):
        return 'verb'
    if grammar.startswith('G:N'):
        return 'noun'
    if grammar.startswith('G:A'):
        return 'adjective'
    return ''


def _outline_signature(nodes):
    return tuple(
        (
            str(node.get('label') or '').lower(),
            _outline_signature(node.get('children') or []),
        )
        for node in nodes or []
    )


def _strip_outline_grammar_labels(nodes):
    stripped = []
    for node in nodes or []:
        cleaned = dict(node)
        cleaned.pop('grammar_label', None)
        cleaned['children'] = _strip_outline_grammar_labels(cleaned.get('children') or [])
        stripped.append(cleaned)
    return stripped


def _parse_hebrew_outline_nodes(full_entry_html):
    raw = str(full_entry_html or '')
    if not raw:
        return []

    segments = re.split(r'<br\s*/?>', raw, flags=re.IGNORECASE)
    has_numbered_outline = any(re.match(r'\s*\d+[a-z]?\d*\)', _strip_html(segment)) for segment in segments)
    if not has_numbered_outline:
        label = _clean_outline_label(raw)
        if not label or label.lower().startswith('aramaic equivalent'):
            return []
        return [{
            'label': label,
            'children': [],
            'count': 0,
            'references': [],
            'reference_groups': [],
        }]

    roots = []
    stack = []
    for segment in segments:
        text = _clean_outline_label(segment)
        if not text or text.lower().startswith('aramaic equivalent'):
            continue
        match = re.match(r'^(\d+)([a-z]?)(\d*)\)\s*(.+)$', text, flags=re.IGNORECASE)
        if not match:
            continue

        letter = match.group(2)
        sub_number = match.group(3)
        if letter and sub_number:
            depth = 3
        elif letter:
            depth = 2
        else:
            depth = 1

        label = match.group(4).strip(' .;:')
        if not label:
            continue
        node = {
            'label': label,
            'children': [],
            'count': 0,
            'references': [],
            'reference_groups': [],
        }

        while len(stack) >= depth:
            stack.pop()
        if stack:
            stack[-1]['children'].append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots


def _greek_outline_label(marker_body, marker_depth):
    body = re.sub(r'<re>.*?</re>', '', str(marker_body or ''), flags=re.DOTALL)
    body = re.split(r'<br\s*/?>', body, maxsplit=1, flags=re.IGNORECASE)[0]
    body = re.split(r'<ref=', body, maxsplit=1)[0]

    bold_match = re.match(r'\s*<b>(.*?)</b>\s*:?', body, flags=re.DOTALL)
    if bold_match:
        return _clean_outline_label(bold_match.group(1))

    plain = _clean_outline_label(body)
    if marker_depth == 1:
        plain = re.split(r'\s*[;:]\s*', plain, maxsplit=1)[0]
    else:
        plain = re.split(r'\s*:\s*', plain, maxsplit=1)[0]
    return plain.strip(' .;:')


def _parse_greek_bold_outline_nodes(full_entry_html):
    raw = str(full_entry_html or '')
    if not raw:
        return []

    labels = []
    for bold_text in re.findall(r'<b>(.*?)</b>', raw, flags=re.DOTALL):
        label = _clean_outline_label(bold_text)
        if not label or re.search(r'[\u0370-\u03FF\u1F00-\u1FFF]', label):
            continue
        if label.lower() in {item.lower() for item in labels}:
            continue
        labels.append(label)

    if not labels:
        return []

    first_label = labels[0]
    children = [
        {
            'label': label,
            'children': [],
            'count': 0,
            'references': [],
            'reference_groups': [],
        }
        for label in labels[1:]
    ]
    return [{
        'label': first_label,
        'children': children,
        'count': 0,
        'references': [],
        'reference_groups': [],
    }]


def _parse_greek_outline_nodes(full_entry_html):
    raw = str(full_entry_html or '')
    if not raw:
        return []

    roots = []
    stack = []
    parts = re.split(r'(?=__\d+\.|__\([a-z]\))', raw, flags=re.IGNORECASE)
    for part in parts:
        top_match = re.match(r'__(\d+)\.\s*(.*)', part, flags=re.DOTALL)
        sub_match = re.match(r'__\(([a-z])\)\s*(.*)', part, flags=re.DOTALL | re.IGNORECASE)
        if top_match:
            depth = 1
            body = top_match.group(2)
        elif sub_match:
            depth = 2
            body = sub_match.group(2)
        else:
            continue

        label = _greek_outline_label(body, depth)
        if not label:
            continue
        refs = []
        for ref_text in re.findall(r"<ref='[^']*'>([^<]+)</ref>", body):
            refs.extend(_expand_reference_blob(ref_text))
        refs = _dedupe_preserve_order(refs)
        node = {
            'label': label,
            'children': [],
            'count': len(refs),
            'references': refs,
            'reference_groups': _chunked(refs, 3),
        }

        while len(stack) >= depth:
            stack.pop()
        if stack:
            stack[-1]['children'].append(node)
        else:
            roots.append(node)
        stack.append(node)

    return roots or _parse_greek_bold_outline_nodes(full_entry_html)


def _lexicon_outline_nodes(strongs_number, language, lexicon_entry):
    if language == 'greek':
        return _parse_greek_outline_nodes((lexicon_entry or {}).get('full_entry') or '')

    base_match = re.search(r'H\d+', str(strongs_number or ''))
    base_code = base_match.group(0) if base_match else _normalize_step_code(strongs_number)
    variant_codes = _variant_step_codes(base_code, 'hebrew') or [base_code]
    outline = []
    seen = set()
    for variant_code in variant_codes:
        entry = _lookup_step_lexicon_entry(variant_code, 'hebrew') or {}
        relation = str(entry.get('relation') or '').lower()
        if 'name of' in relation or 'part of' in relation:
            continue
        nodes = _parse_hebrew_outline_nodes(entry.get('full_entry') or '')
        if not nodes:
            continue
        signature = _outline_signature(nodes)
        if signature in seen:
            continue
        seen.add(signature)
        grammar_label = _grammar_label(entry.get('grammar') or '')
        if grammar_label:
            nodes = [dict(node) for node in nodes]
            nodes[0]['grammar_label'] = grammar_label
        outline.extend(nodes)

    if len(outline) <= 1:
        return _strip_outline_grammar_labels(outline)
    return outline


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


def _dedupe_preserve_order(values):
    ordered = []
    seen = set()
    for value in values or []:
        normalized = str(value or '').strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _chunked(values, size):
    items = list(values or [])
    if size <= 0:
        return [items] if items else []
    return [items[index:index + size] for index in range(0, len(items), size)]


def _normalize_step_code(raw_code):
    code = str(raw_code or '').strip().strip('{}[](),.;:')
    if not code:
        return ''
    return code.replace('=', '').strip()


def _normalize_strongs_base_code(raw_code):
    code = _normalize_step_code(raw_code).upper()
    match = re.match(r'^([GH])0*(\d+)', code)
    if not match:
        return code
    return f'{match.group(1)}{int(match.group(2))}'


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


def _step_reference_to_display(reference_prefix):
    match = re.match(r'^([^.]+)\.(\d+)\.(\d+)(?:\(\d+\.\d+\))?$', str(reference_prefix or '').strip())
    if not match:
        return str(reference_prefix or '').strip()
    return f'{match.group(1)}.{match.group(2)}:{match.group(3)}'


def _parse_token_with_transliteration(value):
    raw = str(value or '').strip()
    match = re.match(r'^(.*?)\s*\((.*?)\)\s*$', raw)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return raw, ''


@lru_cache(maxsize=2)
def _stepbible_usage_index(language):
    file_map = _STEPBIBLE_OT_FILES if language == 'hebrew' else _STEPBIBLE_NT_FILES
    exact_usage = {}
    base_usage = {}
    seen_paths = set()

    for filename in file_map.values():
        if filename in seen_paths:
            continue
        seen_paths.add(filename)
        path = _stepbible_root() / 'Translators Amalgamated OT+NT' / filename
        with path.open('r', encoding='utf-8') as handle:
            for raw_line in handle:
                line = raw_line.rstrip('\n')
                if not line or line.startswith('#'):
                    continue
                ref_token = line.split('\t', 1)[0]
                if '#' not in ref_token:
                    continue
                reference = _step_reference_to_display(ref_token.split('#', 1)[0])
                if not reference:
                    continue
                for code in _dedupe_preserve_order(_extract_step_codes(line)):
                    exact_usage.setdefault(code, []).append(reference)
                    base_code = re.sub(r'([A-Za-z]+)$', '', code) or code
                    base_usage.setdefault(base_code, []).append(reference)
                    normalized_base_code = _normalize_strongs_base_code(base_code)
                    if normalized_base_code and normalized_base_code != base_code:
                        base_usage.setdefault(normalized_base_code, []).append(reference)

    return {
        'exact': {code: _dedupe_preserve_order(refs) for code, refs in exact_usage.items()},
        'base': {code: _dedupe_preserve_order(refs) for code, refs in base_usage.items()},
    }


def _clean_hebrew_surface(value):
    cleaned = str(value or '').replace('/', '').replace('\\', '').strip()
    return re.sub(r'\s+', ' ', cleaned)


def _clean_translation_label(value):
    normalized = str(value or '').replace('/', ' ').strip()
    normalized = normalized.split('»', 1)[0]
    normalized = normalized.split('|', 1)[0]
    normalized = normalized.split('@', 1)[0]
    normalized = normalized.replace('<', '[').replace('>', ']')
    return re.sub(r'\s+', ' ', normalized)


_HEBREW_LETTER_INFO = {
    'א': ('Aleph', 'silent / glottal', 1, 'ox'),
    'ב': ('Bet', 'b / v', 2, 'house'),
    'ג': ('Gimel', 'g', 3, 'camel'),
    'ד': ('Dalet', 'd', 4, 'door'),
    'ה': ('He', 'h', 5, 'window / breath'),
    'ו': ('Vav', 'v / w', 6, 'hook'),
    'ז': ('Zayin', 'z', 7, 'weapon'),
    'ח': ('Chet', 'ch', 8, 'fence'),
    'ט': ('Tet', 't', 9, 'traditional image varies'),
    'י': ('Yod', 'y', 10, 'hand'),
    'כ': ('Kaf', 'k / ch', 20, 'palm'),
    'ך': ('Final Kaf', 'ch', 20, 'palm'),
    'ל': ('Lamed', 'l', 30, 'goad'),
    'מ': ('Mem', 'm', 40, 'water'),
    'ם': ('Final Mem', 'm', 40, 'water'),
    'נ': ('Nun', 'n', 50, 'fish'),
    'ן': ('Final Nun', 'n', 50, 'fish'),
    'ס': ('Samekh', 's', 60, 'support'),
    'ע': ('Ayin', 'silent / glottal', 70, 'eye'),
    'פ': ('Pe', 'p / f', 80, 'mouth'),
    'ף': ('Final Pe', 'f', 80, 'mouth'),
    'צ': ('Tsadi', 'ts', 90, 'traditional image varies'),
    'ץ': ('Final Tsadi', 'ts', 90, 'traditional image varies'),
    'ק': ('Qof', 'q / k', 100, 'traditional image varies'),
    'ר': ('Resh', 'r', 200, 'head'),
    'ש': ('Shin / Sin', 'sh / s', 300, 'tooth'),
    'ת': ('Tav', 't', 400, 'mark'),
}

_HEBREW_LETTER_RE = re.compile(r'[\u05D0-\u05EA]')
_HEBREW_COMPONENT_RE = re.compile(
    r'(?P<strong>[GH]\d+[A-Za-z]?)(?:=(?P<value>[^=/{}/\\]+))?(?:=(?P<gloss>[^/{}/\\]+))?'
)
_HEBREW_TRADITIONAL_IMAGES_NL = {
    'ox': 'os', 'house': 'huis', 'camel': 'kameel', 'door': 'deur',
    'window / breath': 'raam / adem', 'hook': 'haak', 'weapon': 'wapen',
    'fence': 'omheining', 'traditional image varies': 'traditioneel verschillend',
    'hand': 'hand', 'palm': 'handpalm', 'goad': 'ossenprikkel', 'water': 'water',
    'fish': 'vis', 'support': 'steun', 'eye': 'oog', 'mouth': 'mond',
    'tooth': 'tand', 'head': 'hoofd', 'mark': 'teken',
}
_HEBREW_LETTER_NAMES_NL = {
    'Aleph': 'Alef', 'Final Kaf': 'Eind-Kaf', 'Final Mem': 'Eind-Mem',
    'Final Nun': 'Eind-Noen', 'Final Pe': 'Eind-Pe', 'Final Tsadi': 'Eind-Tsadi',
    'Samekh': 'Samech', 'Qof': 'Kof', 'Resh': 'Resj', 'Shin': 'Sjin', 'Sin': 'Sin',
}


def _hebrew_letter_data(text):
    letters = []
    text = str(text or '')
    for character in text:
        if character in _HEBREW_LETTER_INFO:
            name, sound, value, image = _HEBREW_LETTER_INFO[character]
            letters.append({
                'glyph': character,
                'name': name,
                'sound': sound,
                'value': value,
                'traditional_image': image,
            })
        elif unicodedata.category(character).startswith('M') and letters:
            letters[-1]['glyph'] += character
    vowels = {
        '\u05b0': 'ə / ∅', '\u05b1': 'ĕ', '\u05b2': 'ă', '\u05b3': 'ŏ',
        '\u05b4': 'i', '\u05b5': 'ē', '\u05b6': 'e', '\u05b7': 'a',
        '\u05b8': 'ā', '\u05b9': 'ō', '\u05ba': 'ō', '\u05bb': 'u', '\u05c7': 'o',
    }
    for letter in letters:
        glyph = letter['glyph']
        if glyph[0] == 'ש':
            if '\u05c2' in glyph:
                letter['name'], letter['sound'] = 'Sin', 's'
            elif '\u05c1' in glyph:
                letter['name'], letter['sound'] = 'Shin', 'sh'
        if '\u05bc' in glyph:
            hard_sounds = {'ב': 'b', 'כ': 'k', 'ך': 'k', 'פ': 'p', 'ף': 'p'}
            letter['sound'] = hard_sounds.get(glyph[0], letter['sound'])
        vowel = next((vowels[mark] for mark in glyph if mark in vowels), '')
        if glyph[0] == 'ו' and (vowel == 'ō' or ('\u05bc' in glyph and not vowel)):
            letter['sound'] = vowel or 'ū'
        else:
            letter['sound'] += vowel
    return letters


def _parse_hebrew_word_components(raw_components, raw_surface='', raw_grammar=''):
    components = []
    for match in _HEBREW_COMPONENT_RE.finditer(str(raw_components or '')):
        strongs_number = _normalize_step_code(match.group('strong'))
        value = str(match.group('value') or '').strip()
        gloss = str(match.group('gloss') or '').strip(' :;')
        value_is_hebrew = bool(_HEBREW_LETTER_RE.search(value))
        component = {
            'strongs_number': strongs_number,
            'surface': value if value_is_hebrew else '',
            'morphology_code': '' if value_is_hebrew else value,
            'gloss': _clean_translation_label(gloss).strip(' :;\t'),
        }
        component['morphology_description'] = _hebrew_morphology_description(component['morphology_code'])

        numeric_match = re.match(r'^H(\d+)', strongs_number)
        numeric_code = int(numeric_match.group(1)) if numeric_match else 0
        if 9001 <= numeric_code <= 9016:
            component['role'] = 'prefix'
        elif 9020 <= numeric_code <= 9039:
            component['role'] = 'suffix'
        elif strongs_number in {'H0853', 'H0854'}:
            component['role'] = 'grammatical'
        elif component['surface']:
            component['role'] = 'root'
        else:
            component['role'] = 'grammatical'
        component['letters'] = _hebrew_letter_data(component['surface'])
        component['gematria_value'] = sum(letter['value'] for letter in component['letters'])
        components.append(component)

    surface_parts = [
        _clean_hebrew_surface(part)
        for part in str(raw_surface or '').split('/')
        if _HEBREW_LETTER_RE.search(part)
    ]
    surface_components = [
        component for component in components
        if component['surface'] or re.fullmatch(r'[A-Za-z][A-Za-z0-9]*', component['morphology_code'])
    ]
    if len(surface_parts) == len(surface_components):
        for component, surface in zip(surface_components, surface_parts):
            component['lemma'] = component['surface']
            component['surface'] = surface
            component['letters'] = _hebrew_letter_data(surface)
            component['gematria_value'] = sum(letter['value'] for letter in component['letters'])

    verb_code = next((
        code for code in str(raw_grammar or '').split('/')
        if re.match(r'^H?Vt', code)
    ), '')
    if verb_code:
        for component in list(components):
            if component['role'] != 'root' or not component.get('lemma'):
                continue
            consonants = ''.join(letter['glyph'][0] for letter in component['letters'])
            lemma_consonants = ''.join(letter['glyph'][0] for letter in _hebrew_letter_data(component['lemma']))
            prefix_consonants = consonants[:2]
            if prefix_consonants not in {'הת', 'מת', 'ית', 'תת', 'את', 'נת'} or consonants[2:] != lemma_consonants:
                continue
            prefix_letters = component['letters'][:2]
            prefix = {
                'strongs_number': '',
                'role': 'prefix',
                'surface': ''.join(letter['glyph'] for letter in prefix_letters),
                'letters': prefix_letters,
                'gematria_value': sum(letter['value'] for letter in prefix_letters),
                'morphology_code': verb_code,
                'gloss': 'Hitpael stem prefix',
                'morphology_description': (
                    'Hitpael (Hithpael) verb-stem formation, not a separate word or a fixed translation. '
                    'This stem often expresses reflexive or repeated action; its meaning depends on the verb and context.'
                ),
            }
            components.insert(components.index(component), prefix)
            component['letters'] = component['letters'][2:]
            component['surface'] = ''.join(letter['glyph'] for letter in component['letters'])
            component['gematria_value'] = sum(letter['value'] for letter in component['letters'])
    return components


@lru_cache(maxsize=1)
def _hebrew_morphology_descriptions():
    path = _stepbible_root() / 'Morphology codes' / (
        'TEHMC - Translators Expansion of Hebrew Morphology Codes - STEPBible.org CC BY.txt'
    )
    if not path.exists():
        return {}

    descriptions = {}
    current_code = ''
    awaiting_description = False
    try:
        with path.open('r', encoding='utf-8') as handle:
            for raw_line in handle:
                line = raw_line.rstrip('\n')
                stripped = line.strip()
                if stripped == '$':
                    current_code = ''
                    awaiting_description = False
                    continue

                full_match = re.match(r'^([A-Z][A-Za-z0-9]*)\s+Function=(.*)$', stripped)
                if full_match:
                    current_code = full_match.group(1)
                    description = _format_hebrew_morphology_attributes(full_match.group(2))
                    if description:
                        descriptions[current_code] = description
                    awaiting_description = not bool(description)
                    continue

                tab_columns = stripped.split('\t')
                if len(tab_columns) >= 3:
                    brief_code = re.match(r'^(?:\d+:)?([A-Za-z][A-Za-z0-9]*)$', tab_columns[0].strip())
                    if brief_code:
                        descriptions.setdefault(brief_code.group(1), tab_columns[2].strip())
                        continue

                brief_match = re.match(r'^\d+:([A-Za-z][A-Za-z0-9]*)\s+\S+\s+(.+)$', stripped)
                if brief_match:
                    descriptions.setdefault(brief_match.group(1), brief_match.group(2).strip())
                    continue

                if current_code and awaiting_description and stripped and not stripped.startswith(('Example:', '"')):
                    descriptions[current_code] = stripped
                    awaiting_description = False
    except OSError:
        return {}
    return descriptions


def _format_hebrew_morphology_attributes(raw_attributes):
    attributes = {}
    for field in str(raw_attributes or '').split(';'):
        key, separator, value = field.partition('=')
        if separator:
            attributes[key.strip()] = value.strip()
        elif field.strip() and 'Function' not in attributes:
            attributes['Function'] = field.strip()
    function = attributes.get('Function', '')
    form = attributes.get('Form', '')
    if not function:
        return ''

    names = {
        'Noun': 'noun', 'Verb': 'verb', 'Preposition': 'preposition',
        'Suffix': 'suffix', 'Prefix': 'prefix', 'Particle': 'particle',
        'Conjunction': 'conjunction', 'Adjective': 'adjective', 'Pronoun': 'pronoun',
        'Punctuation': 'punctuation', 'Article': 'article', 'Numeral': 'numeral',
    }
    function_name = names.get(function, function.lower())
    if function == 'Noun' and form == 'Proper':
        parts = ['proper noun']
    elif function == 'Noun' and form == 'Common':
        parts = ['common noun']
    elif form:
        form_names = {
            'Definite': 'definite', 'Personal': 'personal', 'Directional': 'directional',
            'Demonstrative': 'demonstrative', 'Interrogative': 'interrogative',
        }
        parts = [form_names.get(form, form.lower()), function_name]
    else:
        parts = [function_name]

    for key, label in (
        ('Person', {'First': 'first person', 'Second': 'second person', 'Third': 'third person'}),
        ('Gender', {'Masculine': 'masculine', 'Feminine': 'feminine', 'Common': 'common gender'}),
        ('Number', {'Singular': 'singular', 'Plural': 'plural', 'Dual': 'dual'}),
        ('State', {'Absolute': 'absolute', 'Construct': 'construct'}),
        ('Tense', {'Perfect': 'perfect', 'Imperfect': 'imperfect', 'Participle': 'participle'}),
        ('Stem', {}),
    ):
        value = attributes.get(key)
        if value:
            parts.append(label.get(value, value.lower()))
    return ', '.join(parts)


def _hebrew_morphology_description(code):
    normalized = str(code or '').strip()
    if not normalized:
        return ''
    descriptions = _hebrew_morphology_descriptions()
    return descriptions.get(normalized) or descriptions.get('H' + normalized, '')


def _hebrew_morphology_details(raw_grammar):
    details = []
    for code in str(raw_grammar or '').split('/'):
        code = code.strip()
        if not code:
            continue
        details.append({
            'code': code,
            'description': _hebrew_morphology_description(code),
        })
    return details


@lru_cache(maxsize=2)
def _stepbible_lexicon(language):
    base = _stepbible_root() / 'Lexicons'
    path = base / (
        'TBESH - Translators Brief lexicon of Extended Strongs for Hebrew - STEPBible.org CC BY.txt'
        if language == 'hebrew'
        else 'TBESG - Translators Brief lexicon of Extended Strongs for Greek - STEPBible.org CC BY.txt'
    )
    exact = {}
    bare_to_first = {}  # maps bare numeric code (e.g. G5083) to first suffixed key found
    with path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.rstrip('\n')
            if not line or not line[:1] in {'G', 'H'}:
                continue
            columns = line.split('\t')
            if len(columns) < 8:
                continue
            variant_codes = _extract_step_codes(columns[1] if len(columns) > 1 else '')
            display_code = _normalize_step_code(
                (variant_codes[0] if variant_codes else '')
                or columns[2]
                or columns[0]
            )
            if not display_code:
                continue
            entry = {
                'strongs_number': display_code,
                'relation': str(columns[1] if len(columns) > 1 else '').strip(),
                'lemma': str(columns[3] or '').strip(),
                'transliteration': str(columns[4] or '').strip(),
                'grammar': str(columns[5] or '').strip(),
                'short_gloss': _clean_translation_label(columns[6] or ''),
                'definition': _strip_html(columns[7] if len(columns) > 7 else ''),
                'full_entry': str(columns[7] if len(columns) > 7 else ''),
                'references': _extract_refs_from_html(columns[7] if len(columns) > 7 else ''),
            }
            exact[display_code] = entry
            # Register bare code (strip trailing letters like G, H, I) pointing to
            # the first suffixed variant so that bare-code lookups still work.
            bare = re.sub(r'[A-Za-z]+$', '', display_code)
            if bare and bare != display_code and bare not in bare_to_first:
                bare_to_first[bare] = display_code
    # Merge bare aliases into the dict so lookups hit in O(1)
    for bare, first_key in bare_to_first.items():
        if bare not in exact:
            exact[bare] = exact[first_key]
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
    candidates = [normalized, _normalize_strongs_base_code(normalized)]

    base = re.sub(r'([A-Za-z_]+)$', '', normalized)
    if base:
        candidates.extend([base, _normalize_strongs_base_code(base)])

    for candidate in _dedupe_preserve_order(candidates):
        if candidate in dictionary:
            return dictionary[candidate]
    return None


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


def _variant_step_codes(base_code, language):
    lexicon = _stepbible_lexicon(language)
    pattern = re.compile(r'^' + re.escape(str(base_code or '')) + r'[A-Za-z]+$')
    return sorted(
        key for key in lexicon.keys()
        if pattern.match(key)
    )


def _first_usage_reference(strongs_number, language):
    normalized = _normalize_step_code(strongs_number)
    if not normalized:
        return ''

    lookup_language = language
    if normalized.startswith('H'):
        lookup_language = 'hebrew'
    elif normalized.startswith('G'):
        lookup_language = 'greek'

    usage_index = _stepbible_usage_index(lookup_language)
    exact_references = usage_index['exact'].get(normalized) or []
    if exact_references:
        return exact_references[0]

    base_code = re.sub(r'([A-Za-z_]+)$', '', normalized) or normalized
    for candidate in _dedupe_preserve_order([base_code, _normalize_strongs_base_code(base_code)]):
        base_references = usage_index['base'].get(candidate) or []
        if base_references:
            return base_references[0]
    return ''


def _variant_label(value):
    text = str(value or '').strip()
    if not text:
        return ''
    if ':' in text:
        text = text.split(':', 1)[1].strip()
    return text.replace('_', ' ')


def _hebrew_translation_counts(strongs_number):
    match = re.search(r'[GH]\d+', str(strongs_number or ''))
    base_code = match.group(0) if match else _normalize_step_code(strongs_number)
    if not base_code:
        return []

    usage_index = _stepbible_usage_index('hebrew')
    counts = []
    for variant_code in _variant_step_codes(base_code, 'hebrew'):
        references = list(usage_index['exact'].get(variant_code) or [])
        if not references:
            continue
        entry = _lookup_step_lexicon_entry(variant_code, 'hebrew') or {}
        label = _variant_label(entry.get('short_gloss') or entry.get('definition') or variant_code)
        if not label:
            continue
        counts.append({
            'label': label,
            'count': len(references),
            'references': references,
            'reference_groups': _chunked(references, 3),
        })

    if counts:
        return counts

    base_references = list(usage_index['base'].get(base_code) or [])
    if not base_references:
        return []

    base_entry = _lookup_step_lexicon_entry(base_code, 'hebrew') or {}
    base_label = _variant_label(base_entry.get('short_gloss') or base_entry.get('definition') or base_code)

    return [{
        'label': base_label,
        'count': len(base_references),
        'references': base_references,
        'reference_groups': _chunked(base_references, 3),
    }]


def _candidate_outline_meanings(structured_definitions, possible_translations):
    headings = _dedupe_preserve_order(
        definition.get('heading')
        for definition in (structured_definitions or [])
        if definition.get('heading')
    )
    return headings or _dedupe_preserve_order(possible_translations)


def _candidate_translation_counts(structured_definitions):
    counts = []
    for definition in structured_definitions or []:
        references = _dedupe_preserve_order(definition.get('references') or [])
        if not references:
            continue
        label = str(definition.get('heading') or definition.get('summary') or '').strip()
        if not label:
            continue
        counts.append({
            'label': label,
            'count': len(references),
            'references': references,
            'reference_groups': _chunked(references, 3),
        })
    return counts


def _displayable_usage_summary(summary):
    text = re.sub(r'\s+', ' ', str(summary or '')).strip(' ,;:')
    if not text:
        return ''
    if re.search(r'[\u0370-\u03FF\u1F00-\u1FFF\u0590-\u05FF\uFB1D-\uFB4F]', text):
        return ''
    if re.search(r'\b(?:Mat|Mrk|Mar|Luk|Jhn|Joh|Act|Rom|Cor|Gal|Eph|Php|Col|Th|Tim|Tit|Phm|Heb|Jas|Jam|Pet|Pe|Jn|Jude|Ju|Rev)\.?\s*\d', text):
        return ''
    return text


def _candidate_usage_outline(candidate):
    lexicon_outline = candidate.get('lexicon_outline') or []
    if lexicon_outline:
        return lexicon_outline

    outline = []
    for definition in candidate.get('structured_definitions') or []:
        label = str(definition.get('heading') or '').strip()
        references = _dedupe_preserve_order(definition.get('references') or [])
        summary = str(definition.get('summary') or '').strip()
        if references and summary:
            reference_text = '|'.join(re.escape(reference) for reference in references)
            summary = re.sub(r'\b(?:' + reference_text + r')\b[,;:\s]*', '', summary).strip(' ,;:')
        summary = _displayable_usage_summary(summary)
        if not label and not summary and not references:
            continue
        outline.append({
            'number': definition.get('number') or len(outline) + 1,
            'label': label,
            'summary': summary,
            'count': len(references),
            'references': references,
            'reference_groups': _chunked(references, 3),
        })

    if outline:
        return outline

    translation_counts = candidate.get('translation_counts') or []
    if translation_counts:
        return [
            {
                'number': index + 1,
                'label': str(item.get('label') or '').strip(),
                'summary': '',
                'count': int(item.get('count') or 0),
                'references': list(item.get('references') or []),
                'reference_groups': list(item.get('reference_groups') or []),
            }
            for index, item in enumerate(translation_counts)
            if str(item.get('label') or '').strip() or item.get('references') or item.get('reference_groups')
        ]

    return [
        {
            'number': index + 1,
            'label': str(label or '').strip(),
            'summary': '',
            'count': 0,
            'references': [],
            'reference_groups': [],
        }
        for index, label in enumerate(candidate.get('outline_meanings') or [])
        if str(label or '').strip()
    ]


def _candidate_core_payload(strongs_number, language, row_data, primary=False):
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
    structured_definitions = _parse_structured_definitions(lexicon_entry.get('full_entry') or '')
    lexicon_outline = _lexicon_outline_nodes(strongs_number, language, lexicon_entry)
    return {
        'strongs_number': normalized_code,
        'first_reference': _first_usage_reference(normalized_code, language),
        'language': 'Hebrew' if language == 'hebrew' else 'Greek',
        'lemma': lemma,
        'transliteration': transliteration,
        'pronunciation': str(os_entry.get('pron') or ''),
        'definition': definition,
        'kjv_definition': kjv_definition,
        'derivation': str(os_entry.get('derivation') or ''),
        'glosses': possible_translations[:12],
        'possible_translations': possible_translations,
        'structured_definitions': structured_definitions,
        'lexicon_outline': lexicon_outline,
        'grammar': str(row_data.get('grammar') or lexicon_entry.get('grammar') or ''),
        'references': _dedupe_preserve_order(lexicon_entry.get('references') or []),
        'lexicon_summary': _strip_html(lexicon_entry.get('full_entry') or ''),
        'blueletter_url': 'https://www.blueletterbible.org/lexicon/{}/kjv/{}/0-1/'.format(
            normalized_code.lower(),
            'wlc' if language == 'hebrew' else 'tr',
        ),
    }


def _related_root_words(derivation, language, exclude_code):
    root_words = []
    seen = set()
    for code in _extract_step_codes(derivation):
        match = re.search(r'[GH]\d+', code)
        normalized_code = match.group(0) if match else _normalize_step_code(code)
        if not normalized_code or normalized_code == exclude_code or normalized_code in seen:
            continue
        seen.add(normalized_code)
        related = _candidate_core_payload(normalized_code, language, {}, primary=False)
        root_words.append({
            'strongs_number': related['strongs_number'],
            'first_reference': related.get('first_reference') or _first_usage_reference(related['strongs_number'], language),
            'lemma': related['lemma'],
            'transliteration': related['transliteration'],
            'definition': related['definition'],
            'possible_meanings': _candidate_outline_meanings(
                related.get('structured_definitions') or [],
                related.get('possible_translations') or [],
            ),
            'blueletter_url': related['blueletter_url'],
        })
        if len(root_words) >= 4:
            break
    return root_words


def _lxx_hebrew_equivalents(strongs_number, language):
    if language != 'greek':
        return []

    normalized = _normalize_step_code(strongs_number)
    if not normalized:
        return []

    entry = _lxx_greek_to_hebrew_index().get(normalized) or {}
    candidates = entry.get('hebrewCandidates') if isinstance(entry, dict) else []
    if not isinstance(candidates, list):
        return []

    normalized_candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        strongs_code = _normalize_step_code(item.get('strong'))
        if not strongs_code:
            continue
        lexicon_entry = _lookup_step_lexicon_entry(strongs_code, 'hebrew') or {}
        open_scriptures = _lookup_open_scriptures_entry(strongs_code, 'hebrew') or {}
        definition = str(
            lexicon_entry.get('definition')
            or open_scriptures.get('strongs_def')
            or ''
        ).strip()
        possible_translations = _meaning_list(
            lexicon_entry.get('short_gloss') or '',
            open_scriptures.get('kjv_def') or '',
            definition,
        )
        structured_definitions = _parse_structured_definitions(lexicon_entry.get('full_entry') or '')
        usage_outline = _lexicon_outline_nodes(strongs_code, 'hebrew', lexicon_entry)
        normalized_candidates.append({
            'strong': strongs_code,
            'first_reference': _first_usage_reference(strongs_code, 'hebrew'),
            'lemma': str(item.get('lemma') or lexicon_entry.get('lemma') or '').strip(),
            'transliteration': str(
                item.get('transliteration')
                or lexicon_entry.get('transliteration')
                or open_scriptures.get('translit')
                or open_scriptures.get('xlit')
                or ''
            ).strip(),
            'definition': definition,
            'possible_meanings': _candidate_outline_meanings(structured_definitions, possible_translations),
            'usage_outline': usage_outline,
            'blueletter_url': 'https://www.blueletterbible.org/lexicon/{}/kjv/wlc/0-1/'.format(
                strongs_code.lower(),
            ),
            'count': int(item.get('count') or 0),
            'percentage': float(item.get('percentage') or 0),
            'confidence': int(item.get('confidence') or 0),
        })
    return normalized_candidates


def _attach_hebrew_outline_counts(outline, translation_counts):
    if not outline or not translation_counts:
        return outline

    def find_best_node(nodes, target_label):
        target = target_label.lower().strip()
        best = None
        best_score = 0

        def walk(node):
            nonlocal best, best_score
            n_lbl = str(node.get('label') or '').lower().strip()
            score = 0
            if target == n_lbl:
                score = 10
            elif target in n_lbl or n_lbl in target:
                score = 5
            elif any(len(w) >= 3 and w in n_lbl for w in re.findall(r'[a-z]+', target)):
                score = 2
            if score > best_score:
                best_score = score
                best = node
            for child in node.get('children', []):
                walk(child)

        for root in nodes:
            walk(root)
        return best if best_score > 0 else None

    if len(outline) == len(translation_counts):
        for node, item in zip(outline, translation_counts):
            node['count'] = int(item.get('count') or 0)
            node['references'] = list(item.get('references') or [])
            node['reference_groups'] = list(item.get('reference_groups') or [])
    else:
        for item in translation_counts:
            matched_node = find_best_node(outline, str(item.get('label') or ''))
            if matched_node and not matched_node.get('count'):
                matched_node['count'] = int(item.get('count') or 0)
                matched_node['references'] = list(item.get('references') or [])
                matched_node['reference_groups'] = list(item.get('reference_groups') or [])

        def rollup(node):
            if node.get('children'):
                child_refs = []
                child_count = 0
                for child in node['children']:
                    rollup(child)
                    child_count += child.get('count', 0)
                    child_refs.extend(child.get('references', []))
                if child_count > 0:
                    node['count'] = child_count
                    node['references'] = _dedupe_preserve_order(child_refs)
                    node['reference_groups'] = _chunked(node['references'], 3)

        for root in outline:
            rollup(root)

    total_count = sum(node.get('count', 0) for node in outline)
    if total_count == 0 and outline:
        merged_refs = []
        for item in translation_counts:
            total_count += int(item.get('count') or 0)
            merged_refs.extend(item.get('references') or [])
        if total_count > 0:
            outline[0]['count'] = total_count
            outline[0]['references'] = _dedupe_preserve_order(merged_refs)
            outline[0]['reference_groups'] = _chunked(outline[0]['references'], 3)

    return outline


def _candidate_payload(strongs_number, language, row_data, primary=False):
    candidate = _candidate_core_payload(strongs_number, language, row_data, primary=primary)
    candidate['source_strongs_number'] = _normalize_step_code(strongs_number)
    candidate['outline_meanings'] = _candidate_outline_meanings(
        candidate.get('structured_definitions') or [],
        candidate.get('possible_translations') or [],
    )
    candidate['reference_groups'] = _chunked(candidate.get('references') or [], 3)
    candidate['translation_counts'] = _candidate_translation_counts(candidate.get('structured_definitions') or [])
    if language == 'hebrew':
        if not candidate['translation_counts']:
            candidate['translation_counts'] = _hebrew_translation_counts(strongs_number)
            if candidate['translation_counts']:
                merged_references = []
                for item in candidate['translation_counts']:
                    merged_references.extend(item.get('references') or [])
                candidate['references'] = _dedupe_preserve_order(merged_references)
                candidate['reference_groups'] = _chunked(candidate['references'], 3)
                candidate['outline_meanings'] = [
                    item['label'] for item in candidate['translation_counts']
                    if str(item.get('label') or '').strip()
                ]
        if candidate.get('lexicon_outline') and candidate.get('translation_counts'):
            candidate['lexicon_outline'] = _attach_hebrew_outline_counts(
                candidate['lexicon_outline'], candidate['translation_counts']
            )

    candidate['usage_outline'] = _candidate_usage_outline(candidate)

    if language == 'greek' and candidate.get('usage_outline'):
        total_greek_count = sum(node.get('count', 0) for node in candidate['usage_outline'])
        if total_greek_count == 0:
            usage_index = _stepbible_usage_index('greek')
            base_code = re.sub(r'([A-Za-z_]+)$', '', candidate['source_strongs_number']) or candidate['source_strongs_number']
            greek_refs = []
            for k in [candidate['source_strongs_number'], base_code, _normalize_strongs_base_code(base_code)]:
                refs = usage_index['exact'].get(k) or usage_index['base'].get(k) or []
                if refs:
                    greek_refs = refs
                    break
            if greek_refs:
                candidate['usage_outline'][0]['count'] = len(greek_refs)
                candidate['usage_outline'][0]['references'] = greek_refs
                candidate['usage_outline'][0]['reference_groups'] = _chunked(greek_refs, 3)

    candidate['root_words'] = _related_root_words(
        candidate.get('derivation') or '',
        language,
        candidate.get('strongs_number') or '',
    )
    candidate['lxx_hebrew_equivalents'] = _lxx_hebrew_equivalents(
        candidate.get('strongs_number') or candidate.get('source_strongs_number') or '',
        language,
    )
    return candidate


def _primary_translation_label(candidates):
    if not candidates:
        return ''

    primary = candidates[0]

    kjv_definition = str(primary.get('kjv_definition') or '').strip()
    if kjv_definition:
        first = re.split(r'[;,/]', kjv_definition)[0].strip(' .')
        if first:
            return _clean_translation_label(first)

    outline = list(primary.get('usage_outline') or primary.get('lexicon_outline') or [])
    if outline and outline[0].get('label'):
        return _clean_translation_label(outline[0]['label'])

    # Prefer the first heading from the structured TBESG outline (richest source)
    structured = list(primary.get('structured_definitions') or [])
    if structured and structured[0].get('heading'):
        return _clean_translation_label(structured[0]['heading'])

    glosses = list(primary.get('glosses') or [])
    if glosses:
        return _clean_translation_label(glosses[0])

    definition = str(primary.get('definition') or '').strip()
    if definition:
        first = re.split(r'[;,/]', definition)[0].strip(' .')
        if first:
            return first

    return ''


def _stepbible_rows_for_verse(book_name, chapter, verse):
    book_code = _stepbible_book_code(book_name)
    reference_prefix = f'{book_code}.{chapter}.{verse}'
    reference = f'{book_code}.{chapter}:{verse}'
    rows = []
    path = _stepbible_file_for_book(book_name)
    with path.open('r', encoding='utf-8') as handle:
        for raw_line in handle:
            line = raw_line.rstrip('\n')
            if not line.startswith(reference_prefix):
                continue
            reference_token, separator, _ = line.partition('#')
            if not separator or _step_reference_to_display(reference_token) != reference:
                continue
            rows.append(line)
    return rows


@lru_cache(maxsize=8)
def _search_stepbible_book_rows(book_name):
    """Index local tagged rows once per book while analysing a complete search."""
    book_code = _stepbible_book_code(book_name)
    rows = {}
    with _stepbible_file_for_book(book_name).open(encoding='utf-8') as handle:
        for line in handle:
            token, separator, _ = line.partition('#')
            if not separator or not token.startswith(book_code + '.'):
                continue
            reference = _step_reference_to_display(token)
            rows.setdefault(reference, []).append(line.rstrip('\n'))
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
        seen_strongs = set()
        for source in [columns[11] if len(columns) > 11 else '', dstrong_grammar, columns[12] if len(columns) > 12 else '']:
            for code in _extract_step_codes(source):
                dedupe_key = _normalize_strongs_base_code(code)
                if dedupe_key and dedupe_key not in seen_strongs:
                    seen_strongs.add(dedupe_key)
                    strongs_numbers.append(code)
        return {
            'surface_text': surface_text,
            'sentence_text': surface_text,
            'transliteration': transliteration,
            'translation_label': translation_label,
            'context_translation': _clean_translation_label(columns[2] if len(columns) > 2 else ''),
            'lemma': str(lemma or '').strip(),
            'definition': _clean_translation_label(gloss),
            'grammar': grammar,
            'strongs_numbers': strongs_numbers,
        }

    raw_surface = str(columns[1] if len(columns) > 1 else '')
    surface_text = _clean_hebrew_surface(raw_surface)
    translation_label = _clean_translation_label(columns[3] if len(columns) > 3 else '')
    grammar = str(columns[5] if len(columns) > 5 else '').strip()
    word_components = _parse_hebrew_word_components(
        columns[11] if len(columns) > 11 else '',
        raw_surface,
        grammar,
    )
    strongs_numbers = []
    seen_strongs = set()
    for source in [columns[8] if len(columns) > 8 else '', columns[4] if len(columns) > 4 else '', columns[9] if len(columns) > 9 else '', columns[11] if len(columns) > 11 else '']:
        for code in _extract_step_codes(source):
            dedupe_key = _normalize_strongs_base_code(code)
            if dedupe_key and dedupe_key not in seen_strongs:
                seen_strongs.add(dedupe_key)
                strongs_numbers.append(code)
    return {
        'surface_text': surface_text,
        'sentence_text': surface_text,
        'transliteration': str(columns[2] if len(columns) > 2 else '').strip(),
        'translation_label': translation_label,
        'context_translation': translation_label,
        'lemma': '',
        'definition': translation_label,
        'grammar': grammar,
        'grammar_details': _hebrew_morphology_details(grammar),
        'word_components': word_components,
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
        'grammar_details': [],
        'word_components': [],
        'hebrew_letters': [],
        'gematria_value': 0,
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

    # Prefer the Open Scriptures KJV definition as the word-cloud label.
    # Fall back to the richer STEP/outline data only when no local Strong's KJV definition is available.
    primary_label = _primary_translation_label(candidates) or str(row_data.get('translation_label') or '')

    return {
        'text': str(row_data.get('surface_text') or ''),
        'sentence_text': str(row_data.get('sentence_text') or row_data.get('surface_text') or ''),
        'lookup_key': lookup_key,
        'clickable': bool(lookup_key),
        'has_candidates': bool(candidates),
        'strongs_count': len(candidates),
        'translation_label': primary_label,
        # Contextual STEPBible gloss for this exact occurrence; drives English word alignment.
        'context_gloss': ' '.join(_dedupe_preserve_order([
            str(row_data.get('context_translation') or '').strip(),
            str(row_data.get('translation_label') or '').strip(),
        ])).strip(),
        'detail_note': '' if candidates else 'This word is aligned in STEPBible, but no lexicon entry was resolved from its Strong\'s tag.',
        'hover_summary': ' | '.join(hover_lines),
        'candidates': candidates,
        'grammar': str(row_data.get('grammar') or ''),
        'grammar_details': list(row_data.get('grammar_details') or []),
        'word_components': list(row_data.get('word_components') or []),
        'hebrew_letters': _hebrew_letter_data(row_data.get('surface_text') or '') if language == 'hebrew' else [],
        'gematria_value': sum(letter['value'] for letter in _hebrew_letter_data(row_data.get('surface_text') or '')) if language == 'hebrew' else 0,
        'tagging_source': 'STEPBible',
    }


def original_text_payload(book_name, chapter, verse):
    cache_key = f'bible_study:original:v21:{book_name}:{chapter}:{verse}'
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


# --- English <-> original language word alignment -------------------------------------------------

# Splits a translated verse into alternating filler / word tokens so the original spacing and
# punctuation can be re-rendered verbatim around the clickable words.
_WORD_SPLIT_RE = re.compile(r"([^\W\d_]+(?:[\u2019']?[^\W\d_]+)*)", re.UNICODE)

# Words that occur in almost every Strong's KJV definition list; matching on them via the
# lexicon produces noise, so they may only align through the contextual STEPBible gloss.
_ENGLISH_FUNCTION_WORDS = {
    'a', 'an', 'the', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by', 'for', 'with', 'from',
    'as', 'that', 'this', 'these', 'those', 'is', 'are', 'was', 'were', 'be', 'been', 'am',
    'it', 'its', 'he', 'she', 'they', 'them', 'him', 'her', 'his', 'their', 'thy', 'thine',
    'thou', 'thee', 'ye', 'you', 'your', 'we', 'us', 'our', 'i', 'my', 'me', 'not', 'no',
    'so', 'then', 'there', 'which', 'who', 'whom', 'shall', 'will', 'did', 'do', 'doth',
    'unto', 'up', 'out', 'into', 'upon', 'one', 'all', 'any', 'every', 'more', 'very',
}

_ENGLISH_IRREGULAR_STEMS = {
    'children': 'child', 'men': 'man', 'women': 'woman', 'people': 'people', 'feet': 'foot',
    'teeth': 'tooth', 'mice': 'mouse', 'geese': 'goose', 'oxen': 'ox', 'brethren': 'brother',
    'wives': 'wife', 'lives': 'life', 'knives': 'knife', 'leaves': 'leaf', 'thieves': 'thief',
    'calves': 'calf', 'halves': 'half', 'loaves': 'loaf', 'selves': 'self', 'staves': 'staff',
    'went': 'go', 'gone': 'go', 'came': 'come', 'said': 'say', 'saith': 'say', 'made': 'make',
    'took': 'take', 'taken': 'take', 'gave': 'give', 'given': 'give', 'saw': 'see', 'seen': 'see',
    'spake': 'speak', 'spoken': 'speak', 'begat': 'beget', 'begotten': 'beget', 'heard': 'hear',
    'knew': 'know', 'known': 'know', 'brought': 'bring', 'bare': 'bear', 'born': 'bear',
    'sons': 'son', 'sat': 'sit', 'stood': 'stand', 'found': 'find', 'built': 'build',
}

_ENGLISH_STEM_SUFFIXES = ('iest', 'ieth', 'ies', 'ied', 'est', 'eth', 'ing', 'ed', 'es', 's')


def _english_stem(word):
    value = str(word or '').lower().replace('\u2019', "'").strip("'")
    if not value:
        return ''
    if value in _ENGLISH_IRREGULAR_STEMS:
        return _ENGLISH_IRREGULAR_STEMS[value]
    if value.endswith('ees'):
        return value[:-1]
    for suffix in _ENGLISH_STEM_SUFFIXES:
        if len(value) - len(suffix) >= 3 and value.endswith(suffix):
            base = value[:-len(suffix)]
            if suffix in {'ies', 'ied', 'iest', 'ieth'}:
                base += 'y'
            return base
    return value


def _english_similar(left, right):
    if left == right:
        return True
    left_stem = _english_stem(left)
    right_stem = _english_stem(right)
    if not left_stem or not right_stem:
        return False
    if left_stem == right_stem:
        return True
    shorter, longer = (left_stem, right_stem) if len(left_stem) <= len(right_stem) else (right_stem, left_stem)
    return len(shorter) >= 4 and longer.startswith(shorter) and len(longer) - len(shorter) <= 3


def _english_words_from(raw):
    return [match.lower() for match in re.findall(r'[A-Za-z]+', str(raw or ''))]


def _alignment_spec_for_word(word):
    """Collect the English surface forms a single original-language token may appear as."""
    gloss_words = set()
    for source in (word.get('context_gloss'), word.get('translation_label')):
        gloss_words.update(_english_words_from(source))

    lexicon_words = set()
    for candidate in word.get('candidates') or []:
        lexicon_words.update(_english_words_from(candidate.get('kjv_definition')))
        for gloss in candidate.get('glosses') or []:
            lexicon_words.update(_english_words_from(gloss))
    lexicon_words -= gloss_words

    return {
        'gloss_words': gloss_words,
        'gloss_stems': {_english_stem(item) for item in gloss_words},
        'lexicon_words': {item for item in lexicon_words if item not in _ENGLISH_FUNCTION_WORDS},
        'lexicon_stems': {_english_stem(item) for item in lexicon_words if item not in _ENGLISH_FUNCTION_WORDS},
    }


def _alignment_score(english_word, spec):
    if english_word in spec['gloss_words']:
        return 6.0
    if any(_english_similar(english_word, gloss) for gloss in spec['gloss_words']):
        return 4.0
    if english_word in _ENGLISH_FUNCTION_WORDS:
        return 0.0
    if english_word in spec['lexicon_words']:
        return 3.0
    if any(_english_similar(english_word, item) for item in spec['lexicon_words']):
        return 2.0
    return 0.0


def _align_english_words(english_words, specs):
    """Monotonic (order preserving) best-score alignment of English words onto original tokens.

    KJV-style English follows the Hebrew/Greek word order closely enough that an order
    preserving alignment avoids the false matches a greedy per-word lookup would produce.
    """
    word_count = len(english_words)
    token_count = len(specs)
    if not word_count or not token_count:
        return [-1] * word_count

    scores = [[_alignment_score(word, spec) for spec in specs] for word in english_words]

    # best[i][j] = best achievable score using english words i.. and original tokens j..
    best = [[0.0] * (token_count + 1) for _ in range(word_count + 1)]
    # 0 = skip english word, 1 = map english word to token j, 2 = advance to token j + 1
    choice = [[0] * (token_count + 1) for _ in range(word_count + 1)]
    for i in range(word_count - 1, -1, -1):
        row = scores[i]
        for j in range(token_count - 1, -1, -1):
            best_value = best[i + 1][j]
            best_choice = 0
            if row[j] > 0 and row[j] + best[i + 1][j] > best_value:
                best_value = row[j] + best[i + 1][j]
                best_choice = 1
            if best[i][j + 1] > best_value:
                best_value = best[i][j + 1]
                best_choice = 2
            best[i][j] = best_value
            choice[i][j] = best_choice

    mapping = [-1] * word_count
    i = 0
    j = 0
    while i < word_count and j < token_count:
        step = choice[i][j]
        if step == 1:
            mapping[i] = j
            i += 1
        elif step == 0:
            i += 1
        else:
            j += 1

    _align_reordered_leftovers(english_words, scores, mapping)
    return mapping


def _align_reordered_leftovers(english_words, scores, mapping):
    """Rescue words the translator moved out of original order (e.g. a trailing proper name).

    Only an unambiguous exact gloss hit on a still unused token is accepted, so this cannot
    introduce the noisy matches that a fully unordered alignment would.
    """
    used_tokens = {index for index in mapping if index >= 0}
    for word_position, token_index in enumerate(mapping):
        if token_index >= 0 or english_words[word_position] in _ENGLISH_FUNCTION_WORDS:
            continue
        matches = [
            index for index, score in enumerate(scores[word_position])
            if score >= 6.0 and index not in used_tokens
        ]
        if len(matches) == 1:
            mapping[word_position] = matches[0]
            used_tokens.add(matches[0])


def english_alignment_payload(book_name, chapter, verse, verse_text, tagged_source='', allow_scoring=True):
    """Map every word of a translated verse onto the index of the original word it renders.

    When the translation has a word-level Strong's tagging the mapping is a direct lookup;
    English translations without tags fall back to the lexicon-scoring alignment.
    """
    text = re.sub(r'\s+', ' ', str(verse_text or '')).strip()
    if not text:
        return {'tokens': [], 'aligned_count': 0, 'method': ''}

    tagged_source = str(tagged_source or '').strip().lower()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:24]
    cache_key = f'bible_study:alignment:v5:{tagged_source}:{int(bool(allow_scoring))}:{book_name}:{chapter}:{verse}:{digest}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        original = original_text_payload(book_name, chapter, verse)
    except Exception:
        original = None

    words = (original or {}).get('words') or []

    parts = _WORD_SPLIT_RE.split(text)
    word_positions = [index for index in range(1, len(parts), 2)]
    display_words = [parts[index].lower() for index in word_positions]

    mapping = None
    method = ''
    if tagged_source in TAGGED_BIBLE_SOURCES:
        mapping = _tagged_mapping(tagged_source, book_name, chapter, verse, display_words, words)
        if mapping is not None:
            method = 'tagged'

    if mapping is None and allow_scoring:
        specs = [_alignment_spec_for_word(word or {}) for word in words]
        mapping = _align_english_words(display_words, specs)
        method = 'lexicon'

    word_index_by_part = {}
    for position, token_index in zip(word_positions, mapping or []):
        if token_index >= 0 and words[token_index].get('clickable'):
            word_index_by_part[position] = token_index

    tokens = []
    for index, part in enumerate(parts):
        if not part:
            continue
        tokens.append({
            'text': part,
            'word_index': word_index_by_part.get(index, -1),
        })

    payload = {
        'tokens': tokens if word_index_by_part else [],
        'aligned_count': len(word_index_by_part),
        'method': method if word_index_by_part else '',
        'tagging_source': TAGGED_BIBLE_SOURCES[tagged_source]['label'] if method == 'tagged' else '',
    }
    cache.set(cache_key, payload, ORIGINAL_TEXT_CACHE_TIMEOUT)
    return payload


# --- Word-level tagged translations (direct Strong's lookup) --------------------------------------

# Public-domain SWORD modules that carry a Strong's number on (nearly) every content word.
TAGGED_BIBLE_SOURCES = {
    'kjv': {
        'label': "CrossWire KJV (1769) with Strong's Numbers",
        'module': 'KJV',
        'url': 'https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/KJV.zip',
    },
    'svv': {
        'label': 'Statenvertaling met Strong-nummers',
        'module': 'DutSVVA',
        'url': 'https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/DutSVVA.zip',
        # Also exported as a selectable local Bible translation.
        'local_bible': 'statenvertaling',
    },
}

# Which tagged edition supplies the word glosses when the site is shown in that language.
GLOSS_SOURCE_BY_LANGUAGE = {
    'nl': 'svv',
}

# Share of displayed words that must be recovered from the tagged text before we trust it; below
# this the shown edition differs too much (e.g. a modern revision) and the tagging is discarded.
_TAGGED_COVERAGE_THRESHOLD = 0.6


def tagged_bible_root():
    return Path(__file__).resolve().parents[2] / 'data' / 'tagged_bibles'


@lru_cache(maxsize=16)
def _tagged_book(source, book_name):
    path = tagged_bible_root() / source / f'{book_name}.json.gz'
    if not path.exists():
        return {}
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    chapters = payload.get('chapters') if isinstance(payload, dict) else None
    return chapters if isinstance(chapters, dict) else {}


def _tagged_segments(source, book_name, chapter, verse):
    return (_tagged_book(source, book_name).get(str(chapter)) or {}).get(str(verse)) or []


def _original_token_indexes_by_code(words):
    """Ordered list of original-language token positions for every Strong's code in the verse."""
    occurrences = {}
    for index, word in enumerate(words or []):
        seen = set()
        for candidate in (word or {}).get('candidates') or []:
            code = _normalize_strongs_base_code(candidate.get('strongs_number'))
            if not code or code in seen:
                continue
            seen.add(code)
            occurrences.setdefault(code, []).append(index)
    return occurrences


def _loose_word_key(value):
    return _strip_marks(str(value or '').lower())


def _loose_words_match(left, right):
    """Tolerate spelling drift between a tagged edition and its modern revision."""
    if left == right:
        return True
    shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
    return len(shorter) >= 4 and longer.startswith(shorter) and len(longer) - len(shorter) <= 3


def _transfer_alignment_by_lcs(source_words, source_mapping, target_words):
    """Carry a mapping from the tagged edition's word sequence onto the displayed word sequence."""
    source_keys = [_loose_word_key(word) for word in source_words]
    target_keys = [_loose_word_key(word) for word in target_words]
    source_count = len(source_keys)
    target_count = len(target_keys)
    lengths = [[0] * (target_count + 1) for _ in range(source_count + 1)]
    for i in range(source_count - 1, -1, -1):
        for j in range(target_count - 1, -1, -1):
            if _loose_words_match(source_keys[i], target_keys[j]):
                lengths[i][j] = lengths[i + 1][j + 1] + 1
            else:
                lengths[i][j] = max(lengths[i + 1][j], lengths[i][j + 1])

    mapping = [-1] * target_count
    matched = 0
    i = 0
    j = 0
    while i < source_count and j < target_count:
        if _loose_words_match(source_keys[i], target_keys[j]):
            mapping[j] = source_mapping[i]
            matched += 1
            i += 1
            j += 1
        elif lengths[i + 1][j] >= lengths[i][j + 1]:
            i += 1
        else:
            j += 1
    return mapping, matched


# Grammatical markers (object marker, article) that a tagged word group only points at when it
# carries no content word; otherwise the content word wins.
_LOW_PRIORITY_STRONGS = {'H853', 'H854', 'G3588'}


def _pick_tagged_token(code, occurrences, consumed, last_assigned):
    """Pick which occurrence of a repeated Strong's number this tagged word group refers to."""
    positions = occurrences.get(code)
    if not positions:
        return None
    free = [position for position in positions if position not in consumed[code]]
    if not free:
        return positions[-1]
    # Nearest still unused occurrence, preferring the forward direction on a tie.
    return min(free, key=lambda position: (abs(position - last_assigned), 0 if position >= last_assigned else 1))


def _tagged_run_assignments(source, book_name, chapter, verse, words):
    """Resolve every tagged word group of a verse to the original-language token it renders."""
    segments = _tagged_segments(source, book_name, chapter, verse)
    if not segments or not words:
        return []

    occurrences = _original_token_indexes_by_code(words)
    if not occurrences:
        return []

    consumed = {code: set() for code in occurrences}
    last_assigned = 0
    assignments = []
    for segment in segments:
        codes = str((segment or [''])[0] or '').split()
        segment_words = (segment or ['', []])[1] or []
        ordered_codes = (
            [code for code in codes if code not in _LOW_PRIORITY_STRONGS]
            + [code for code in codes if code in _LOW_PRIORITY_STRONGS]
        )

        token_index = -1
        for code in ordered_codes:
            picked = _pick_tagged_token(code, occurrences, consumed, last_assigned)
            if picked is None:
                continue
            consumed[code].add(picked)
            token_index = picked
            last_assigned = picked
            break

        assignments.append((token_index, list(segment_words)))
    return assignments


def _tagged_mapping(source, book_name, chapter, verse, display_words, words):
    assignments = _tagged_run_assignments(source, book_name, chapter, verse, words)
    if not assignments or not display_words:
        return None

    source_words = []
    source_mapping = []
    for token_index, segment_words in assignments:
        for segment_word in segment_words:
            source_words.append(str(segment_word).lower())
            source_mapping.append(token_index)

    mapping, matched = _transfer_alignment_by_lcs(source_words, source_mapping, display_words)
    if matched < len(display_words) * _TAGGED_COVERAGE_THRESHOLD:
        return None
    return mapping


@lru_cache(maxsize=4)
def _tagged_usage_index(source):
    """Concordance of how the tagged edition renders each Strong's number, most frequent first."""
    path = tagged_bible_root() / source / '_usage.json.gz'
    if not path.exists():
        return {}
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def strongs_word_summary(code, language_code='en'):
    normalized = _normalize_strongs_base_code(code)
    if not re.fullmatch(r'[HG]\d+', normalized):
        raise ValueError('Invalid Strong\'s number.')
    language = 'hebrew' if normalized.startswith('H') else 'greek'
    entry = (_lookup_step_lexicon_entry(str(code).upper(), language)
             or _lookup_step_lexicon_entry(normalized, language)
             or _lookup_step_lexicon_entry(normalized[0] + normalized[1:].zfill(4), language))
    if not entry:
        raise ValueError('Strong\'s entry not found.')
    source = GLOSS_SOURCE_BY_LANGUAGE.get(str(language_code).lower()[:2])
    local_usage = _tagged_usage_index(source).get(normalized, []) if source else []
    return {
        'strongs_number': normalized,
        'source_strongs_number': entry['strongs_number'],
        'lemma': entry.get('lemma', ''),
        'transliteration': entry.get('transliteration', ''),
        'gloss': entry.get('short_gloss', ''),
        'local_gloss': str(local_usage[0][0]) if local_usage else '',
        'language': 'Hebrew' if language == 'hebrew' else 'Greek',
    }


def strongs_word_detail(code, language_code='en'):
    summary = strongs_word_summary(code, language_code)
    language = 'hebrew' if summary['language'] == 'Hebrew' else 'greek'
    code = summary['strongs_number']
    entry_code = summary['source_strongs_number']
    candidate = _candidate_payload(entry_code, language, {})
    candidate['strongs_number'] = code
    source = GLOSS_SOURCE_BY_LANGUAGE.get(str(language_code)[:2])
    if source:
        candidate['local_usage'] = [
            {'label': item[0], 'count': item[1], 'references': item[2] if len(item) > 2 else []}
            for item in _tagged_usage_index(source).get(summary['strongs_number'], [])[:12]
        ]
    letters = _hebrew_letter_data(summary['lemma']) if language == 'hebrew' else []
    components = []
    if language == 'hebrew':
        service = 9001 <= int(code[1:]) <= 9039 or int(code[1:]) in {853, 854}
        components = [{
            'strongs_number': candidate['source_strongs_number'],
            'surface': summary['lemma'], 'lemma': summary['lemma'],
            'role': 'grammatical' if service else 'root',
            'gloss': summary['gloss'], 'local_gloss': summary['local_gloss'], 'letters': letters,
        }]
    return {
        'detail_kind': 'lemma',
        'language_code': 'hbo' if language == 'hebrew' else 'grc',
        'language_label': summary['language'],
        'words': [{
            'text': summary['lemma'], 'clickable': True, 'has_candidates': True,
            'candidates': [candidate], 'word_components': components,
            'hebrew_letters': letters,
            'gematria_value': sum(letter['value'] for letter in letters),
        }],
    }


def strongs_occurrence_word_detail(code, book, chapter, verse, word_index, language_code='en'):
    """Use the exact tagged token, including its inflection and component morphology."""
    summary = strongs_word_summary(code)
    language = original_language_code(book)
    lines = _search_stepbible_book_rows(book).get(f'{_stepbible_book_code(book)}.{chapter}:{verse}', [])
    rows = [_parse_stepbible_row(line, language) for line in lines]
    rows = [row for row in rows if row and str(row.get('surface_text') or '').strip()]
    if word_index < 0 or word_index >= len(rows):
        raise ValueError('Original word occurrence not found.')
    row = rows[word_index]
    if summary['strongs_number'] not in {
        _normalize_strongs_base_code(item) for item in row.get('strongs_numbers') or []
    }:
        raise ValueError('Original word occurrence does not match the Strong\'s number.')
    word = _token_payload_from_step_row(row, language)
    if str(language_code).lower()[:2] in GLOSS_SOURCE_BY_LANGUAGE:
        localized = localized_original_text_payload(book, chapter, verse, language_code)
        localized_words = localized.get('words') or []
        if word_index >= len(localized_words) or localized_words[word_index]['text'] != word['text']:
            raise ValueError('Localized original word occurrence does not match the tagged token.')
        word = localized_words[word_index]
    return {
        'detail_kind': 'occurrence',
        'book': book, 'chapter': chapter, 'verse': verse,
        'language_code': 'hbo' if language == 'hebrew' else 'grc',
        'language_label': summary['language'],
        'words': [word],
        'local_source_name': TAGGED_BIBLE_SOURCES[GLOSS_SOURCE_BY_LANGUAGE[str(language_code).lower()[:2]]]['label']
        if str(language_code).lower()[:2] in GLOSS_SOURCE_BY_LANGUAGE else '',
    }


def strongs_occurrence_references(code, versification='nrsv'):
    summary = strongs_word_summary(code)
    language = 'hebrew' if summary['language'] == 'Hebrew' else 'greek'
    usage = _stepbible_usage_index(language)
    references = (usage['exact'].get(summary['source_strongs_number'], [])
                  if re.fullmatch(r'[HGhg]\d+[A-Za-z]+', str(code))
                  else usage['base'].get(summary['strongs_number'], []))
    normalized = []
    for reference in references:
        match = re.match(r'^([^.]+)\.(\d+)[.:](\d+)', reference)
        if not match:
            raise ValueError('Invalid concordance reference.')
        chapter, start, end = int(match[2]), int(match[3]), int(match[3])
        if versification == 'kjv' and '[' in reference:
            alternate = re.search(r'\[(\d+)\.(\d+)[a-z]?(?:-(\d+)[a-z]?)?\]', reference)
            if not alternate:
                raise ValueError('Unsupported KJV concordance numbering.')
            chapter = int(alternate[1])
            start = int(alternate[2])
            end = int(alternate[3] or start)
        normalized.extend(f'{match[1]}.{chapter}:{verse}' for verse in range(start, end + 1))
    book_order = {
        _stepbible_book_code(book).lower(): index
        for index, book in enumerate([*_STEPBIBLE_OT_FILES, *_STEPBIBLE_NT_FILES])
    }
    def sort_key(reference):
        book, position = reference.split('.', 1)
        chapter, verse = position.split(':')
        return book_order[book.lower()], int(chapter), int(verse)
    return sorted({ref for ref in normalized if not ref.endswith(':0')}, key=sort_key)


def search_strongs_dictionary(query, language_code='en'):
    """Search local lexicon labels, original lemmas and tagged Dutch renderings."""
    query = str(query).strip()
    if re.fullmatch(r'[HGhg]0*\d+', query):
        try:
            return [strongs_word_summary(query.upper(), language_code)]
        except ValueError:
            return []
    terms = _WORD_SPLIT_RE.findall(_strip_marks(query).casefold())
    if not terms:
        return []
    source = GLOSS_SOURCE_BY_LANGUAGE.get(str(language_code)[:2], 'svv')
    local_usage = _tagged_usage_index(source)
    found = {}
    for language in ('hebrew', 'greek'):
        for code, entry in _stepbible_lexicon(language).items():
            normalized = _normalize_strongs_base_code(code)
            labels = ' '.join(str(item[0]) for item in local_usage.get(normalized, []))
            haystack = _strip_marks(' '.join([
                entry.get('lemma', ''), entry.get('transliteration', ''),
                entry.get('short_gloss', ''), labels,
            ])).casefold()
            words = _WORD_SPLIT_RE.findall(haystack)
            if all(any(term == word or _english_stem(term) == _english_stem(word) for word in words)
                   for term in terms):
                if normalized not in found:
                    found[normalized] = dict(strongs_word_summary(code, language_code), source_strongs_numbers=[])
                source_code = entry['strongs_number']
                if source_code not in found[normalized]['source_strongs_numbers']:
                    found[normalized]['source_strongs_numbers'].append(source_code)
    return sorted(found.values(), key=lambda item: (item['strongs_number'][0], int(item['strongs_number'][1:])))


def search_result_word_study(results, query, tagged_source='', allow_scoring=False, language_code='en'):
    """Reverse existing verse-word alignment using only local tagged/lexicon data."""
    query_terms = {word.casefold() for word in _WORD_SPLIT_RE.findall(query)}
    query_stems = {_english_stem(word) for word in query_terms} if tagged_source == 'kjv' or allow_scoring else set()
    found = {}
    unaligned = 0
    for result in results:
        book, chapter, verse = result['book'], result['chapter'], result['verse']
        language = original_language_code(book)
        lines = _search_stepbible_book_rows(book).get(f'{_stepbible_book_code(book)}.{chapter}:{verse}', [])
        rows = [_parse_stepbible_row(line, language) for line in lines]
        rows = [row for row in rows if row and str(row.get('surface_text') or '').strip()]
        words = []
        for row in rows:
            candidates = []
            for code in row.get('strongs_numbers') or []:
                entry = _lookup_step_lexicon_entry(code, language) or {}
                candidates.append({'strongs_number': code, 'glosses': [entry.get('short_gloss', '')]})
            words.append({
                'candidates': candidates, 'clickable': bool(candidates),
                'context_gloss': row.get('context_translation', ''),
                'translation_label': row.get('translation_label', ''),
            })
        displayed = _WORD_SPLIT_RE.findall(_strip_html(result.get('text', '')))
        mapping = _tagged_mapping(tagged_source, book, chapter, verse,
                                  [word.casefold() for word in displayed], words) if tagged_source else None
        method = 'tagged'
        if mapping is None and allow_scoring:
            mapping = _align_english_words([word.casefold() for word in displayed],
                                          [_alignment_spec_for_word(word) for word in words])
            method = 'lexicon'
        if mapping is None:
            unaligned += 1
            continue
        for text, index in zip(displayed, mapping):
            if index < 0 or (text.casefold() not in query_terms and _english_stem(text) not in query_stems):
                continue
            for candidate in words[index]['candidates']:
                code = _normalize_strongs_base_code(candidate['strongs_number'])
                if code.startswith('H') and int(code[1:]) >= 9000:
                    continue
                if code not in found:
                    found[code] = dict(strongs_word_summary(code, language_code), matched_references=[],
                                       matched_occurrences=[], alignment_method=method)
                if result['reference'] not in found[code]['matched_references']:
                    found[code]['matched_references'].append(result['reference'])
                occurrence = {
                    'book': book, 'chapter': chapter, 'verse': verse, 'word_index': index,
                    'reference': result['reference'], 'text': rows[index]['surface_text'],
                    'source_strongs_number': candidate['strongs_number'],
                }
                if occurrence not in found[code]['matched_occurrences']:
                    found[code]['matched_occurrences'].append(occurrence)
    return {'candidates': list(found.values()), 'unaligned_results': unaligned}


def localized_original_text_payload(book_name, chapter, verse, language_code='en'):
    """Original-language payload enriched with glosses from a tagged edition in the UI language."""
    source = GLOSS_SOURCE_BY_LANGUAGE.get(str(language_code or '').strip().lower()[:2])
    payload = original_text_payload(book_name, chapter, verse)
    if not source:
        return payload

    cache_key = f'bible_study:original-local:v11:{source}:{book_name}:{chapter}:{verse}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    words = payload.get('words') or []
    phrases_by_token = {}
    phrases_by_component = {}
    tagged_segments = _tagged_segments(source, book_name, chapter, verse)
    assignments = _tagged_run_assignments(source, book_name, chapter, verse, words)
    for segment, (token_index, segment_words) in zip(tagged_segments, assignments):
        if token_index < 0 or not segment_words:
            continue
        phrase = ' '.join(segment_words)
        phrases_by_token.setdefault(token_index, []).append(phrase)
        for code in _extract_step_codes((segment or [''])[0]):
            base_code = _normalize_strongs_base_code(code)
            phrases_by_component.setdefault((token_index, base_code), []).append(phrase)

    usage_index = _tagged_usage_index(source)
    enriched = copy.deepcopy(payload)

    unresolved_words = []
    unresolved_components = []
    unresolved_morphology = []
    for index, word in enumerate(enriched.get('words') or []):
        word['local_gloss'] = ' '.join(_dedupe_preserve_order(phrases_by_token.get(index) or []))
        for candidate in word.get('candidates') or []:
            code = _normalize_strongs_base_code(candidate.get('strongs_number'))
            candidate['local_usage'] = [
                {
                    'label': str(entry[0]),
                    'count': int(entry[1]),
                    'references': list(entry[2]) if len(entry) > 2 and isinstance(entry[2], list) else [],
                }
                for entry in (usage_index.get(code) or [])[:12]
                if isinstance(entry, (list, tuple)) and len(entry) >= 2
            ]
        # Words the tagged edition left untagged still get its most common rendering.
        if not word['local_gloss']:
            primary_usage = ((word.get('candidates') or [{}])[0] or {}).get('local_usage') or []
            word['local_gloss'] = str(primary_usage[0]['label']) if primary_usage else ''

        if not word['local_gloss'] and word.get('clickable'):
            raw_en = str(word.get('context_gloss') or word.get('translation_label') or '').strip()
            clean_en = re.sub(r'\[.*?\]|<.*?>', '', raw_en)
            clean_en = re.sub(r'\s+', ' ', clean_en).strip(' -.,;:')
            unresolved_words.append((word, clean_en or raw_en))

        for component in word.get('word_components') or []:
            component_code = _normalize_strongs_base_code(component.get('strongs_number'))
            exact_phrases = _dedupe_preserve_order(phrases_by_component.get((index, component_code)) or [])
            if exact_phrases:
                component['local_gloss'] = ' '.join(exact_phrases)
            else:
                local_renderings = usage_index.get(component_code) or []
                component['local_gloss'] = str(local_renderings[0][0]) if local_renderings else ''
            if not component['local_gloss'] and component.get('gloss'):
                raw_component_gloss = str(component.get('gloss') or '').strip()
                clean_component_gloss = re.sub(r'\[.*?\]|<.*?>', '', raw_component_gloss)
                clean_component_gloss = re.sub(r'\s+', ' ', clean_component_gloss).strip(' -.,;:')
                if source == 'svv' and component.get('morphology_code') in {'Op2m', 'Op2f', 'Pp2m', 'Pp2f'} and clean_component_gloss.lower() == 'you':
                    component['local_gloss'] = 'jullie'
                else:
                    unresolved_components.append((component, clean_component_gloss or raw_component_gloss))

            if component.get('morphology_description'):
                unresolved_morphology.append((component, str(component['morphology_description']).strip()))

        for morphology in word.get('grammar_details') or []:
            if morphology.get('description'):
                unresolved_morphology.append((morphology, str(morphology['description']).strip()))

    if unresolved_words or unresolved_components or unresolved_morphology:
        try:
            from walkasjesus_app.views.user_preferences import _translate_google_batch
            texts_to_translate = _dedupe_preserve_order(
                text for _, text in unresolved_words + unresolved_components + unresolved_morphology if text
            )
            if texts_to_translate:
                translated = _translate_google_batch(texts_to_translate, language_code)
                translated_by_text = dict(zip(texts_to_translate, translated))
                for word, text in unresolved_words:
                    if translated_by_text.get(text):
                        word['local_gloss'] = translated_by_text[text].strip()
                for component, text in unresolved_components:
                    if translated_by_text.get(text):
                        component['local_gloss'] = translated_by_text[text].strip()
                for morphology, text in unresolved_morphology:
                    if translated_by_text.get(text):
                        morphology['local_description'] = translated_by_text[text].strip()
        except Exception:
            pass

    enriched['local_language'] = str(language_code or '')[:2]
    enriched['local_source_name'] = TAGGED_BIBLE_SOURCES[source]['label']
    if str(language_code or '').strip().lower()[:2] == 'nl':
        for word in enriched.get('words') or []:
            for letter in word.get('hebrew_letters') or []:
                letter['name_local'] = _HEBREW_LETTER_NAMES_NL.get(letter.get('name'), letter.get('name', ''))
                letter['traditional_image_local'] = _HEBREW_TRADITIONAL_IMAGES_NL.get(
                    letter.get('traditional_image'), letter.get('traditional_image', '')
                )
            for component in word.get('word_components') or []:
                for letter in component.get('letters') or []:
                    letter['name_local'] = _HEBREW_LETTER_NAMES_NL.get(letter.get('name'), letter.get('name', ''))
                    letter['traditional_image_local'] = _HEBREW_TRADITIONAL_IMAGES_NL.get(
                        letter.get('traditional_image'), letter.get('traditional_image', '')
                    )
    enriched['selected_word'] = next((word for word in enriched['words'] if word['clickable']), None)
    cache.set(cache_key, enriched, ORIGINAL_TEXT_CACHE_TIMEOUT)
    return enriched