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
            'count': 0,
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
    match = re.match(r'^([^.]+)\.(\d+)\.(\d+)$', str(reference_prefix or '').strip())
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
            'blueletter_url': 'https://www.blueletterbible.org/lexicon/{}/kjv/wlc/0-1/'.format(
                strongs_code.lower(),
            ),
            'count': int(item.get('count') or 0),
            'percentage': float(item.get('percentage') or 0),
            'confidence': int(item.get('confidence') or 0),
        })
    return normalized_candidates


def _candidate_payload(strongs_number, language, row_data, primary=False):
    candidate = _candidate_core_payload(strongs_number, language, row_data, primary=primary)
    candidate['source_strongs_number'] = _normalize_step_code(strongs_number)
    candidate['outline_meanings'] = _candidate_outline_meanings(
        candidate.get('structured_definitions') or [],
        candidate.get('possible_translations') or [],
    )
    candidate['reference_groups'] = _chunked(candidate.get('references') or [], 3)
    candidate['translation_counts'] = _candidate_translation_counts(candidate.get('structured_definitions') or [])
    if language == 'hebrew' and not candidate['translation_counts']:
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
    candidate['usage_outline'] = _candidate_usage_outline(candidate)
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
        'detail_note': '' if candidates else 'This word is aligned in STEPBible, but no lexicon entry was resolved from its Strong\'s tag.',
        'hover_summary': ' | '.join(hover_lines),
        'candidates': candidates,
        'grammar': str(row_data.get('grammar') or ''),
        'tagging_source': 'STEPBible',
    }


def original_text_payload(book_name, chapter, verse):
    cache_key = f'bible_study:original:v12:{book_name}:{chapter}:{verse}'
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