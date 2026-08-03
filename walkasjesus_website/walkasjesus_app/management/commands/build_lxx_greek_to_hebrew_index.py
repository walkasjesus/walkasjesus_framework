import csv
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from walkasjesus_app.lib.strongs_service import (
    _lookup_open_scriptures_entry,
    _lookup_step_lexicon_entry,
    _normalize_step_code,
    _stepbible_lexicon,
    _stepbible_usage_index,
)


REQUIRED_FIELDS = {'greek_strong', 'hebrew_strong'}
OPTIONAL_FIELDS = {
    'greek_lemma',
    'hebrew_lemma',
    'hebrew_transliteration',
    'count',
    'weight',
    'reference',
}
_LXX_NOTE_RE = re.compile(r'\[in\s+LXX(?P<note>.*?);\]', re.IGNORECASE)
_HEBREW_TERM_RE = re.compile(r'[\u0590-\u05FF]+')


def _repo_root():
    return Path(__file__).resolve().parents[3]


def _default_output_path():
    return _repo_root() / 'data' / 'lxx_greek_to_hebrew.json'


def _default_evidence_path():
    return _repo_root() / 'data' / 'lxx_alignment_evidence.tsv'


def _default_tbesg_path():
    return _repo_root() / 'data' / 'stepbible' / 'Lexicons' / 'TBESG - Translators Brief lexicon of Extended Strongs for Greek - STEPBible.org CC BY.txt'


def _available_tagot_files():
    return sorted((_repo_root() / 'data' / 'stepbible' / 'Translators Amalgamated OT+NT').glob('TAGOT*.txt'))


def _normalized_fieldnames(reader):
    return [str(field or '').strip().lower() for field in (reader.fieldnames or []) if str(field or '').strip()]


def _safe_count(row):
    raw = row.get('count') or row.get('weight') or '1'
    try:
        parsed = int(float(str(raw).strip()))
    except (TypeError, ValueError):
        parsed = 1
    return max(1, parsed)


def _merge_meta(existing, incoming):
    merged = dict(existing or {})
    for key, value in (incoming or {}).items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


def _base_strongs_code(value):
    normalized = _normalize_step_code(value)
    if not normalized:
        return ''
    return re.sub(r'([A-Za-z_]+)$', '', normalized)


def _strip_marks(value):
    normalized = unicodedata.normalize('NFD', str(value or ''))
    return ''.join(ch for ch in normalized if unicodedata.category(ch) != 'Mn')


def _normalize_hebrew_lemma(value):
    compact = _strip_marks(value)
    compact = compact.replace('־', '').replace('׳', '').replace('״', '')
    return ''.join(ch for ch in compact if '\u0590' <= ch <= '\u05FF')


def _coarse_pos(grammar):
    text = str(grammar or '').strip().upper()
    match = re.search(r':[A-Z]+', text)
    if not match:
        return ''
    return match.group(0).lstrip(':')


def _extract_lxx_note(full_entry):
    match = _LXX_NOTE_RE.search(str(full_entry or ''))
    return str(match.group('note') or '').strip() if match else ''


def _extract_hebrew_terms(note_text):
    ordered = []
    seen = set()
    for term in _HEBREW_TERM_RE.findall(str(note_text or '')):
        normalized = _normalize_hebrew_lemma(term)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(term)
    return ordered


def _lxx_primary_weight(note_text, index):
    if index != 0:
        return 1
    if re.search(r'chiefly\s+for|always\s+for|mostly\s+for|usually\s+for', str(note_text or ''), re.IGNORECASE):
        return 3
    return 1


def _hebrew_lemma_to_strongs_map():
    mapping = defaultdict(list)
    for entry in _stepbible_lexicon('hebrew').values():
        strong = _base_strongs_code(entry.get('strongs_number'))
        lemma = _normalize_hebrew_lemma(entry.get('lemma'))
        if not strong or not lemma:
            continue
        candidate = {
            'strong': strong,
            'pos': _coarse_pos(entry.get('grammar')),
        }
        if candidate not in mapping[lemma]:
            mapping[lemma].append(candidate)
    return mapping


def _nt_greek_strongs():
    usage_index = _stepbible_usage_index('greek')
    return {
        _base_strongs_code(code)
        for code in (usage_index.get('base') or {}).keys()
        if _base_strongs_code(code).startswith('G')
    }


def _load_tbesg_fallback_rows(allowed_greek=None):
    if not _default_tbesg_path().exists():
        return []

    nt_greek = allowed_greek or _nt_greek_strongs()
    hebrew_index = _hebrew_lemma_to_strongs_map()
    rows = []
    seen_greek = set()

    for entry in _stepbible_lexicon('greek').values():
        greek = _base_strongs_code(entry.get('strongs_number'))
        if not greek or greek in seen_greek or (nt_greek and greek not in nt_greek):
            continue
        seen_greek.add(greek)
        greek_pos = _coarse_pos(entry.get('grammar'))

        note_text = _extract_lxx_note(entry.get('full_entry'))
        if not note_text:
            continue

        hebrew_terms = _extract_hebrew_terms(note_text)
        emitted = set()
        for index, lemma in enumerate(hebrew_terms):
            normalized = _normalize_hebrew_lemma(lemma)
            matches = list(hebrew_index.get(normalized, []))
            same_pos_matches = [candidate for candidate in matches if candidate.get('pos') and candidate.get('pos') == greek_pos]
            if same_pos_matches:
                matches = same_pos_matches
            for candidate in matches:
                hebrew = candidate.get('strong')
                if hebrew in emitted:
                    continue
                emitted.add(hebrew)
                rows.append({
                    'greek_strong': greek,
                    'greek_lemma': str(entry.get('lemma') or '').strip(),
                    'hebrew_strong': hebrew,
                    'hebrew_lemma': str((_lookup_step_lexicon_entry(hebrew, 'hebrew') or {}).get('lemma') or lemma).strip(),
                    'hebrew_transliteration': str((_lookup_step_lexicon_entry(hebrew, 'hebrew') or {}).get('transliteration') or '').strip(),
                    'count': str(_lxx_primary_weight(note_text, index)),
                    'reference': 'TBESG LXX note',
                })
    return rows


def _greek_meta(strongs_number, row):
    normalized = _normalize_step_code(strongs_number)
    lexicon_entry = _lookup_step_lexicon_entry(normalized, 'greek') or {}
    open_scriptures = _lookup_open_scriptures_entry(normalized, 'greek') or {}
    return {
        'strong': normalized,
        'lemma': str(row.get('greek_lemma') or lexicon_entry.get('lemma') or '').strip(),
        'transliteration': str(
            lexicon_entry.get('transliteration')
            or open_scriptures.get('translit')
            or open_scriptures.get('xlit')
            or ''
        ).strip(),
    }


def _hebrew_meta(strongs_number, row):
    normalized = _normalize_step_code(strongs_number)
    lexicon_entry = _lookup_step_lexicon_entry(normalized, 'hebrew') or {}
    open_scriptures = _lookup_open_scriptures_entry(normalized, 'hebrew') or {}
    return {
        'strong': normalized,
        'lemma': str(row.get('hebrew_lemma') or lexicon_entry.get('lemma') or '').strip(),
        'transliteration': str(
            row.get('hebrew_transliteration')
            or lexicon_entry.get('transliteration')
            or open_scriptures.get('translit')
            or open_scriptures.get('xlit')
            or ''
        ).strip(),
    }


def _candidate_confidence(count, total, runner_up_count):
    if total <= 0 or count <= 0:
        return 0
    share_score = (count / total) * 100.0
    dominance_score = 100.0 if runner_up_count <= 0 else max(0.0, min(100.0, (1.0 - (runner_up_count / count)) * 100.0))
    sample_score = 0.0 if total <= 1 else min(100.0, (math.log10(total) / math.log10(500.0)) * 100.0)
    confidence = (0.5 * share_score) + (0.2 * dominance_score) + (0.3 * sample_score)
    return int(round(max(0.0, min(99.0, confidence))))


def _load_evidence_rows(evidence_path):
    delimiter = '\t' if evidence_path.suffix.lower() != '.csv' else ','
    with evidence_path.open('r', encoding='utf-8', newline='') as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        fieldnames = set(_normalized_fieldnames(reader))
        missing = REQUIRED_FIELDS - fieldnames
        if missing:
            raise CommandError(
                f'Evidence file {evidence_path} is missing required column(s): {", ".join(sorted(missing))}. '
                'Expected TSV/CSV columns include greek_strong and hebrew_strong.'
            )
        for row in reader:
            normalized = {
                str(key or '').strip().lower(): str(value or '').strip()
                for key, value in row.items()
                if str(key or '').strip()
            }
            yield normalized


def _build_index(rows, min_count, min_percentage, allowed_greek=None):
    pair_counts = defaultdict(Counter)
    greek_meta = {}
    hebrew_meta = {}

    for row in rows:
        greek = _normalize_step_code(row.get('greek_strong'))
        hebrew = _normalize_step_code(row.get('hebrew_strong'))
        if not greek or not hebrew or not greek.startswith('G') or not hebrew.startswith('H'):
            continue
        if allowed_greek and greek not in allowed_greek:
            continue

        count = _safe_count(row)
        pair_counts[greek][hebrew] += count
        greek_meta[greek] = _merge_meta(greek_meta.get(greek), _greek_meta(greek, row))
        hebrew_meta[hebrew] = _merge_meta(hebrew_meta.get(hebrew), _hebrew_meta(hebrew, row))

    payload = {}
    for greek, counts in sorted(pair_counts.items()):
        ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        total = sum(counts.values())
        runner_up_count = ordered[1][1] if len(ordered) > 1 else 0
        candidates = []
        for index, (hebrew, count) in enumerate(ordered):
            percentage = round((count / total) * 100.0, 1) if total else 0.0
            if index > 0 and (count < min_count or percentage < min_percentage):
                continue
            meta = hebrew_meta.get(hebrew, {})
            candidates.append({
                'strong': hebrew,
                'lemma': str(meta.get('lemma') or '').strip(),
                'transliteration': str(meta.get('transliteration') or '').strip(),
                'count': count,
                'percentage': percentage,
                'confidence': _candidate_confidence(count, total, runner_up_count),
            })
        if not candidates:
            continue
        meta = greek_meta.get(greek, {})
        payload[greek] = {
            'greekStrong': greek,
            'greekLemma': str(meta.get('lemma') or '').strip(),
            'greekTransliteration': str(meta.get('transliteration') or '').strip(),
            'hebrewCandidates': candidates,
        }
    return payload


class Command(BaseCommand):
    help = (
        'Build a reusable Greek Strong\'s -> Hebrew Strong\'s index from normalized Septuagint translation evidence '
        'and write it to data/lxx_greek_to_hebrew.json.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--evidence-file',
            type=str,
            default='',
            help=(
                'TSV or CSV file containing normalized LXX alignment evidence. Required columns: '
                'greek_strong, hebrew_strong. Optional: greek_lemma, hebrew_lemma, hebrew_transliteration, count.'
            ),
        )
        parser.add_argument(
            '--output',
            type=str,
            default=str(_default_output_path()),
            help='Destination JSON path. Defaults to data/lxx_greek_to_hebrew.json.',
        )
        parser.add_argument(
            '--min-count',
            type=int,
            default=1,
            help='Minimum occurrence count for non-top Hebrew candidates. Default: 1.',
        )
        parser.add_argument(
            '--min-percentage',
            type=float,
            default=0.0,
            help='Minimum percentage for non-top Hebrew candidates. Default: 0.0.',
        )
        parser.add_argument(
            '--greek-strong',
            action='append',
            dest='greek_strongs',
            default=[],
            help='Optional Greek Strong\'s code to limit generation. Repeat for multiple values.',
        )

    def handle(self, *args, **options):
        evidence_arg = str(options.get('evidence_file') or '').strip()
        evidence_path = Path(evidence_arg) if evidence_arg else _default_evidence_path()
        output_path = Path(str(options.get('output') or '').strip() or _default_output_path())
        min_count = max(1, int(options.get('min_count') or 1))
        min_percentage = max(0.0, float(options.get('min_percentage') or 0.0))
        greek_filter = {
            _normalize_step_code(value)
            for value in (options.get('greek_strongs') or [])
            if _normalize_step_code(value)
        }

        fallback_used = False
        if evidence_path.exists():
            rows = list(_load_evidence_rows(evidence_path))
        else:
            rows = _load_tbesg_fallback_rows(allowed_greek=greek_filter or None)
            if not rows:
                tagot_files = _available_tagot_files()
                raise CommandError(
                    'No normalized LXX alignment evidence file was found at '
                    f'{evidence_path}. This repository checkout also does not contain the STEPBible TAGOT Greek OT files '
                    'needed for direct offline extraction, and no fallback rows could be derived from TBESG LXX notes. '
                    'Provide --evidence-file with a TSV/CSV of Greek/Hebrew pairings or add the missing TAGOT source files. '
                    f'TAGOT files detected: {len(tagot_files)}.'
                )
            fallback_used = True

        index_payload = _build_index(rows, min_count=min_count, min_percentage=min_percentage, allowed_greek=greek_filter or None)
        if not index_payload:
            raise CommandError('No Greek-to-Hebrew mappings were produced from the supplied evidence file.')

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open('w', encoding='utf-8') as handle:
            json.dump(index_payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')

        total_candidates = sum(len(entry.get('hebrewCandidates') or []) for entry in index_payload.values())
        detail = ' using TBESG LXX-note fallback evidence' if fallback_used else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'Built {len(index_payload)} Greek Strong mappings with {total_candidates} Hebrew candidates into {output_path}{detail}'
            )
        )