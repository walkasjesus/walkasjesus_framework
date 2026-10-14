import gzip
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from bible_lib import BibleBooks as BibleLibBibleBooks
from django.core.management.base import BaseCommand, CommandError

from walkasjesus_app.lib.strongs_service import (
    TAGGED_BIBLE_SOURCES,
    _normalize_strongs_base_code,
    tagged_bible_root,
)
from walkasjesus_app.models.bibles import local_bible_root

# How many distinct renderings of a Strong's number to keep in the concordance.
_MAX_USAGE_ENTRIES = 15

# pysword book names -> walkasjesus BibleBooks enum names
_PYSWORD_BOOK_NAMES = {
    'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers',
    'Deuteronomy': 'Deuteronomy', 'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth',
    'I Samuel': 'SamuelFirstBook', 'II Samuel': 'SamuelSecondBook',
    'I Kings': 'KingsFirstBook', 'II Kings': 'KingsSecondBook',
    'I Chronicles': 'ChroniclesFirstBook', 'II Chronicles': 'ChroniclesSecondBook',
    'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah', 'Esther': 'Esther', 'Job': 'Job',
    'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
    'Song of Solomon': 'SongOfSolomon', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
    'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel',
    'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos', 'Obadiah': 'Obadiah',
    'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk',
    'Zephaniah': 'Zephaniah', 'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi',
    'Matthew': 'Matthew', 'Mark': 'Mark', 'Luke': 'Luke', 'John': 'John', 'Acts': 'Acts',
    'Romans': 'Romans', 'I Corinthians': 'CorinthiansFirstBook', 'II Corinthians': 'CorinthiansSecondBook',
    'Galatians': 'Galatians', 'Ephesians': 'Ephesians', 'Philippians': 'Philippians',
    'Colossians': 'Colossians', 'I Thessalonians': 'ThessaloniansFirstBook',
    'II Thessalonians': 'ThessaloniansSecondBook', 'I Timothy': 'TimothyFirstBook',
    'II Timothy': 'TimothySecondBook', 'Titus': 'Titus', 'Philemon': 'Philemon',
    'Hebrews': 'Hebrews', 'James': 'James', 'I Peter': 'PeterFirstBook', 'II Peter': 'PeterSecondBook',
    'I John': 'JohnFirstBook', 'II John': 'JohnSecondBook', 'III John': 'JohnThirdBook',
    'Jude': 'Jude', 'Revelation of John': 'Revelation',
}

# Study notes and psalm headings are not part of the verse text the site renders.
_STRIP_BLOCK_RE = re.compile(r'<(note|title)\b[^>]*>.*?</\1>|<(?:note|title)\b[^>]*/>', re.DOTALL | re.IGNORECASE)
_W_TAG_RE = re.compile(r'<w\b[^>]*>.*?</w>|<w\b[^>]*/>', re.DOTALL)
_LEMMA_RE = re.compile(r'lemma="([^"]*)"')
_STRONG_RE = re.compile(r'strong:([GH]\d+[A-Za-z]?)', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_WORD_RE = re.compile(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)*", re.UNICODE)

# Highest real dictionary entries; anything above is an Online Bible parsing code, not a lemma.
_MAX_HEBREW_STRONGS = 8674
_MAX_GREEK_STRONGS = 5624


def _is_lexical_strongs(code):
    match = re.match(r'^([GH])(\d+)$', str(code or ''))
    if not match:
        return False
    number = int(match.group(2))
    limit = _MAX_HEBREW_STRONGS if match.group(1) == 'H' else _MAX_GREEK_STRONGS
    return 1 <= number <= limit


def _clean_text_from_osis(raw_verse):
    """The plain verse text as a reader sees it, without study notes or markup."""
    body = _STRIP_BLOCK_RE.sub(' ', raw_verse or '')
    text = _TAG_RE.sub('', body)
    text = text.replace('\u00b6', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return re.sub(r'\s+([,.;:!?])', r'\1', text)


def _segments_from_osis(raw_verse):
    """Split a raw OSIS verse into [strongs_codes, [words]] runs, keeping the original word order."""
    body = _STRIP_BLOCK_RE.sub(' ', raw_verse or '')
    segments = []
    position = 0
    for match in _W_TAG_RE.finditer(body):
        untagged = _WORD_RE.findall(_TAG_RE.sub(' ', body[position:match.start()]))
        if untagged:
            segments.append(['', untagged])

        chunk = match.group(0)
        lemma = _LEMMA_RE.search(chunk)
        codes = []
        for raw_code in _STRONG_RE.findall(lemma.group(1) if lemma else ''):
            code = _normalize_strongs_base_code(raw_code)
            if code and code not in codes and _is_lexical_strongs(code):
                codes.append(code)
        words = _WORD_RE.findall(_TAG_RE.sub(' ', chunk))
        if words:
            segments.append([' '.join(codes), words])
        position = match.end()

    trailing = _WORD_RE.findall(_TAG_RE.sub(' ', body[position:]))
    if trailing:
        segments.append(['', trailing])
    return segments


class Command(BaseCommand):
    help = (
        'Build the word-level Strong\'s index for a tagged translation from its CrossWire SWORD '
        'module. Requires the optional pysword package (pip install pysword).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'source',
            nargs='?',
            default='all',
            choices=sorted(TAGGED_BIBLE_SOURCES) + ['all'],
            help='Which tagged translation to build.',
        )
        parser.add_argument(
            '--module-path',
            default='',
            help='Path to an already extracted SWORD module directory (containing mods.d/).',
        )

    def handle(self, *args, **options):
        try:
            from pysword.modules import SwordModules
        except ImportError as error:
            raise CommandError('pysword is required for this command: pip install pysword') from error

        requested = str(options['source'])
        sources = sorted(TAGGED_BIBLE_SOURCES) if requested == 'all' else [requested]
        module_path = str(options['module_path'] or '').strip()
        if module_path and len(sources) > 1:
            raise CommandError('--module-path can only be used with a single source')

        for source in sources:
            definition = TAGGED_BIBLE_SOURCES[source]
            with tempfile.TemporaryDirectory() as workdir:
                path = module_path or self._download_module(definition['url'], Path(workdir))
                modules = SwordModules(path)
                available = modules.parse_modules()
                if definition['module'] not in available:
                    raise CommandError(
                        f'Module {definition["module"]} not found in {path}: {sorted(available)}'
                    )
                self._build(source, modules.get_bible_from_module(definition['module']))

    def _download_module(self, url, workdir):
        self.stdout.write(f'Downloading SWORD module from {url} ...')
        archive = workdir / 'module.zip'
        with urllib.request.urlopen(url, timeout=180) as response, archive.open('wb') as handle:
            shutil.copyfileobj(response, handle)
        target = workdir / 'module'
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(target)
        return str(target)

    def _build(self, source, bible):
        definition = TAGGED_BIBLE_SOURCES[source]
        output_root = tagged_bible_root() / source
        output_root.mkdir(parents=True, exist_ok=True)

        local_bible_key = definition.get('local_bible')
        text_root = None
        if local_bible_key:
            text_root = local_bible_root() / local_bible_key
            text_root.mkdir(parents=True, exist_ok=True)

        books = bible.get_structure().get_books()
        total_verses = 0
        total_tagged = 0
        usage = defaultdict(Counter)
        usage_references = defaultdict(lambda: defaultdict(list))

        for testament in ('ot', 'nt'):
            for book in books.get(testament, []):
                enum_name = _PYSWORD_BOOK_NAMES.get(book.name)
                if not enum_name:
                    continue

                chapters = {}
                texts = {}
                for chapter_number, verse_count in enumerate(book.chapter_lengths, start=1):
                    verses = {}
                    chapter_texts = {}
                    for verse_number in range(1, verse_count + 1):
                        raw = ''.join(bible.get_iter(
                            books=[book.name],
                            chapters=[chapter_number],
                            verses=[verse_number],
                            clean=False,
                        ))
                        clean_text = _clean_text_from_osis(raw)
                        if clean_text:
                            chapter_texts[str(verse_number)] = clean_text

                        segments = _segments_from_osis(raw)
                        if not any(codes for codes, _ in segments):
                            continue
                        verses[str(verse_number)] = segments
                        total_verses += 1
                        for codes, segment_words in segments:
                            if not codes or not segment_words:
                                continue
                            total_tagged += 1
                            phrase = ' '.join(segment_words).lower()
                            book_code = BibleLibBibleBooks.abbreviation(BibleLibBibleBooks[enum_name])
                            book_code = book_code[:2] + book_code[2:].lower() if book_code[:1].isdigit() else book_code[:1] + book_code[1:].lower()
                            reference = f'{book_code}.{chapter_number}:{verse_number}'
                            for code in codes.split():
                                usage[code][phrase] += 1
                                if reference not in usage_references[code][phrase]:
                                    usage_references[code][phrase].append(reference)
                    if verses:
                        chapters[str(chapter_number)] = verses
                    if chapter_texts:
                        texts[str(chapter_number)] = chapter_texts

                payload = {
                    'book': enum_name,
                    'source': definition['label'],
                    'chapters': chapters,
                }
                with gzip.open(output_root / f'{enum_name}.json.gz', 'wt', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, separators=(',', ':'))

                if text_root is not None and texts:
                    with gzip.open(text_root / f'{enum_name}.json.gz', 'wt', encoding='utf-8') as handle:
                        json.dump(
                            {'book': enum_name, 'source': definition['label'], 'chapters': texts},
                            handle, ensure_ascii=False, separators=(',', ':'),
                        )

        concordance = {}
        for code, counter in usage.items():
            renderings = []
            for phrase, count in counter.most_common(_MAX_USAGE_ENTRIES):
                renderings.append([phrase, count, usage_references[code][phrase]])
            concordance[code] = renderings
        with gzip.open(output_root / '_usage.json.gz', 'wt', encoding='utf-8') as handle:
            json.dump(concordance, handle, ensure_ascii=False, separators=(',', ':'))

        self.stdout.write(self.style.SUCCESS(
            f'{source}: wrote {total_verses} verses with {total_tagged} tagged word groups '
            f'and {len(concordance)} Strong\'s renderings to {output_root}'
        ))
