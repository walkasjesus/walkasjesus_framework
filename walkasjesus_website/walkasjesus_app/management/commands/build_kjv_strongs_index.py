import gzip
import json
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from walkasjesus_app.lib.strongs_service import (
    TAGGED_KJV_SOURCE_NAME,
    _normalize_strongs_base_code,
    tagged_bible_root,
)

DEFAULT_MODULE_URL = 'https://www.crosswire.org/ftpmirror/pub/sword/packages/rawzip/KJV.zip'

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

_W_TAG_RE = re.compile(r'<w\b[^>]*>.*?</w>|<w\b[^>]*/>', re.DOTALL)
_LEMMA_RE = re.compile(r'lemma="([^"]*)"')
_STRONG_RE = re.compile(r'strong:([GH]\d+[A-Za-z]?)', re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_WORD_RE = re.compile(r"[A-Za-z]+(?:['\u2019][A-Za-z]+)*")


def _segments_from_osis(raw_verse):
    """Split a raw OSIS KJV verse into [strongs_codes, [words]] runs, keeping word order."""
    segments = []
    position = 0
    for match in _W_TAG_RE.finditer(raw_verse or ''):
        plain = _TAG_RE.sub(' ', raw_verse[position:match.start()])
        untagged = _WORD_RE.findall(plain)
        if untagged:
            segments.append(['', untagged])

        chunk = match.group(0)
        lemma = _LEMMA_RE.search(chunk)
        codes = []
        for code in _STRONG_RE.findall(lemma.group(1) if lemma else ''):
            normalized = _normalize_strongs_base_code(code)
            if normalized and normalized not in codes:
                codes.append(normalized)
        words = _WORD_RE.findall(_TAG_RE.sub(' ', chunk))
        if words:
            segments.append([' '.join(codes), words])
        position = match.end()

    trailing = _WORD_RE.findall(_TAG_RE.sub(' ', raw_verse[position:]))
    if trailing:
        segments.append(['', trailing])
    return segments


class Command(BaseCommand):
    help = (
        'Build the word-level Strong\'s index for the KJV from the CrossWire SWORD module. '
        'Requires the optional pysword package (pip install pysword).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--module-path',
            default='',
            help='Path to an already extracted SWORD module directory (containing mods.d/).',
        )
        parser.add_argument(
            '--module-url',
            default=DEFAULT_MODULE_URL,
            help='URL of the raw SWORD module zip to download when --module-path is not given.',
        )
        parser.add_argument('--module-name', default='KJV', help='SWORD module name to read.')

    def handle(self, *args, **options):
        try:
            from pysword.modules import SwordModules
        except ImportError as error:
            raise CommandError('pysword is required for this command: pip install pysword') from error

        with tempfile.TemporaryDirectory() as workdir:
            module_path = str(options['module_path'] or '').strip()
            if not module_path:
                module_path = self._download_module(options['module_url'], Path(workdir))

            modules = SwordModules(module_path)
            available = modules.parse_modules()
            module_name = str(options['module_name'])
            if module_name not in available:
                raise CommandError(f'Module {module_name} not found in {module_path}: {sorted(available)}')
            bible = modules.get_bible_from_module(module_name)
            self._build(bible)

    def _download_module(self, url, workdir):
        self.stdout.write(f'Downloading SWORD module from {url} ...')
        archive = workdir / 'module.zip'
        with urllib.request.urlopen(url, timeout=120) as response, archive.open('wb') as handle:
            shutil.copyfileobj(response, handle)
        target = workdir / 'module'
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extractall(target)
        return str(target)

    def _build(self, bible):
        output_root = tagged_bible_root() / 'kjv_strongs'
        output_root.mkdir(parents=True, exist_ok=True)

        structure = bible.get_structure()
        books = structure.get_books()
        total_verses = 0
        total_tagged = 0

        for testament in ('ot', 'nt'):
            for book in books.get(testament, []):
                enum_name = _PYSWORD_BOOK_NAMES.get(book.name)
                if not enum_name:
                    continue

                chapters = {}
                for chapter_number, verse_count in enumerate(book.chapter_lengths, start=1):
                    verses = {}
                    for verse_number in range(1, verse_count + 1):
                        raw = ''.join(bible.get_iter(
                            books=[book.name],
                            chapters=[chapter_number],
                            verses=[verse_number],
                            clean=False,
                        ))
                        segments = _segments_from_osis(raw)
                        if not segments:
                            continue
                        verses[str(verse_number)] = segments
                        total_verses += 1
                        total_tagged += sum(1 for codes, _ in segments if codes)
                    if verses:
                        chapters[str(chapter_number)] = verses

                payload = {
                    'book': enum_name,
                    'source': TAGGED_KJV_SOURCE_NAME,
                    'chapters': chapters,
                }
                target = output_root / f'{enum_name}.json.gz'
                with gzip.open(target, 'wt', encoding='utf-8') as handle:
                    json.dump(payload, handle, ensure_ascii=False, separators=(',', ':'))
                self.stdout.write(f'  {enum_name}: {sum(len(v) for v in chapters.values())} verses')

        self.stdout.write(self.style.SUCCESS(
            f'Wrote {total_verses} verses with {total_tagged} tagged word groups to {output_root}'
        ))
