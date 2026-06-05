import re
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from walkasjesus_app.lib.sword_commentary import normalize_book_key
from walkasjesus_app.models import SwordCommentaryEntry, SwordCommentarySource


OSIS_TO_BOOK = {
    'Gen': 'Genesis',
    'Exod': 'Exodus',
    'Lev': 'Leviticus',
    'Num': 'Numbers',
    'Deut': 'Deuteronomy',
    'Josh': 'Joshua',
    'Judg': 'Judges',
    'Ruth': 'Ruth',
    '1Sam': '1 Samuel',
    '2Sam': '2 Samuel',
    '1Kgs': '1 Kings',
    '2Kgs': '2 Kings',
    '1Chr': '1 Chronicles',
    '2Chr': '2 Chronicles',
    'Ezra': 'Ezra',
    'Neh': 'Nehemiah',
    'Esth': 'Esther',
    'Job': 'Job',
    'Ps': 'Psalms',
    'Prov': 'Proverbs',
    'Eccl': 'Ecclesiastes',
    'Song': 'Song of Solomon',
    'Isa': 'Isaiah',
    'Jer': 'Jeremiah',
    'Lam': 'Lamentations',
    'Ezek': 'Ezekiel',
    'Dan': 'Daniel',
    'Hos': 'Hosea',
    'Joel': 'Joel',
    'Amos': 'Amos',
    'Obad': 'Obadiah',
    'Jonah': 'Jonah',
    'Mic': 'Micah',
    'Nah': 'Nahum',
    'Hab': 'Habakkuk',
    'Zeph': 'Zephaniah',
    'Hag': 'Haggai',
    'Zech': 'Zechariah',
    'Mal': 'Malachi',
    'Matt': 'Matthew',
    'Mark': 'Mark',
    'Luke': 'Luke',
    'John': 'John',
    'Acts': 'Acts',
    'Rom': 'Romans',
    '1Cor': '1 Corinthians',
    '2Cor': '2 Corinthians',
    'Gal': 'Galatians',
    'Eph': 'Ephesians',
    'Phil': 'Philippians',
    'Col': 'Colossians',
    '1Thess': '1 Thessalonians',
    '2Thess': '2 Thessalonians',
    '1Tim': '1 Timothy',
    '2Tim': '2 Timothy',
    'Titus': 'Titus',
    'Phlm': 'Philemon',
    'Heb': 'Hebrews',
    'Jas': 'James',
    '1Pet': '1 Peter',
    '2Pet': '2 Peter',
    '1John': '1 John',
    '2John': '2 John',
    '3John': '3 John',
    'Jude': 'Jude',
    'Rev': 'Revelation',
}


def normalize_commentary_text(value):
    text = str(value or '').replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


class Command(BaseCommand):
    help = 'Import local CrossWire SWORD commentary modules into the database.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source-id',
            action='append',
            default=[],
            help='Import only specific source id(s) from SWORD_COMMENTARY_IMPORT_SOURCES.',
        )

    def handle(self, *args, **options):
        if not self._has_mod2osis_binary() and not self._has_mod2imp_binary():
            raise CommandError('Could not find "mod2osis" or "mod2imp" in PATH. Install CrossWire SWORD tools first (for example: brew install sword).')

        configured_sources = getattr(settings, 'SWORD_COMMENTARY_IMPORT_SOURCES', [])
        if not isinstance(configured_sources, (list, tuple)) or not configured_sources:
            raise CommandError('SWORD_COMMENTARY_IMPORT_SOURCES is empty or invalid.')

        requested_source_ids = {str(item).strip() for item in options.get('source_id', []) if str(item).strip()}
        import_count = 0

        for config in configured_sources:
            source_id = str(config.get('id', '')).strip()
            if not source_id:
                continue
            if requested_source_ids and source_id not in requested_source_ids:
                continue

            import_count += 1
            self._import_source(config)

        if requested_source_ids and import_count == 0:
            raise CommandError('No matching source id found in SWORD_COMMENTARY_IMPORT_SOURCES.')

        self.stdout.write(self.style.SUCCESS(f'Imported {import_count} SWORD source(s).'))

    def _has_mod2osis_binary(self):
        return shutil.which('mod2osis') is not None

    def _has_mod2imp_binary(self):
        return shutil.which('mod2imp') is not None

    def _iter_osis_entries(self, module_name, module_root):
        env = dict(os.environ)
        env['SWORD_PATH'] = str(module_root)

        process = subprocess.Popen(
            ['mod2osis', module_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        if process.stdout is None:
            raise CommandError(f'Failed to capture OSIS output for module {module_name}.')

        try:
            for _, elem in ET.iterparse(process.stdout, events=('end',)):
                if not str(elem.tag).endswith('verse'):
                    continue

                osis_id = str(elem.attrib.get('osisID', '')).strip()
                match = re.match(r'^([^.]+)\.(\d+)\.(\d+)$', osis_id)
                if not match:
                    elem.clear()
                    continue

                book_code, chapter_raw, verse_raw = match.groups()
                book_name = OSIS_TO_BOOK.get(book_code)
                if not book_name:
                    elem.clear()
                    continue

                text = normalize_commentary_text(''.join(elem.itertext()))
                if text:
                    yield (book_name, normalize_book_key(book_name), int(chapter_raw), int(verse_raw), text)

                elem.clear()
        finally:
            stderr_output = process.stderr.read().decode('utf-8', errors='ignore') if process.stderr else ''
            return_code = process.wait()
            if return_code != 0:
                raise CommandError(f'mod2osis failed for module {module_name}: {stderr_output.strip()}')

    def _parse_mod2imp_key(self, raw_key):
        key = str(raw_key or '').strip()
        match = re.match(r'^(?P<book>.+?)\s+(?P<chapter>\d+):(?P<verse>\d+)(?:-\d+)?$', key)
        if not match:
            return None

        return (
            match.group('book').strip(),
            int(match.group('chapter')),
            int(match.group('verse')),
        )

    def _iter_mod2imp_entries(self, module_name, module_root):
        env = dict(os.environ)
        env['SWORD_PATH'] = str(module_root)

        process = subprocess.Popen(
            ['mod2imp', module_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            encoding='utf-8',
            errors='ignore',
        )

        if process.stdout is None:
            raise CommandError(f'Failed to capture mod2imp output for module {module_name}.')

        current_key = None
        current_lines = []

        def flush_entry():
            if not current_key:
                return None
            parsed = self._parse_mod2imp_key(current_key)
            if not parsed:
                return None

            book_name, chapter, verse = parsed
            text = normalize_commentary_text('\n'.join(current_lines))
            if not text:
                return None

            return (book_name, normalize_book_key(book_name), chapter, verse, text)

        try:
            for raw_line in process.stdout:
                line = raw_line.rstrip('\n')
                if line.startswith('$$$'):
                    flushed = flush_entry()
                    if flushed:
                        yield flushed
                    current_key = line[3:].strip()
                    current_lines = []
                    continue

                if current_key is None:
                    continue

                current_lines.append(line)

            flushed = flush_entry()
            if flushed:
                yield flushed
        finally:
            stderr_output = process.stderr.read().strip() if process.stderr else ''
            return_code = process.wait()
            if return_code != 0:
                raise CommandError(f'mod2imp failed for module {module_name}: {stderr_output}')

    def _iter_entries(self, module_name, module_root, import_format='auto'):
        fmt = str(import_format or 'auto').strip().lower()

        if fmt == 'mod2imp':
            if not self._has_mod2imp_binary():
                raise CommandError('Configured import_format="mod2imp" but "mod2imp" is not available in PATH.')
            yield from self._iter_mod2imp_entries(module_name, module_root)
            return

        if fmt == 'mod2osis':
            if not self._has_mod2osis_binary():
                raise CommandError('Configured import_format="mod2osis" but "mod2osis" is not available in PATH.')
            yield from self._iter_osis_entries(module_name, module_root)
            return

        if not self._has_mod2osis_binary() and self._has_mod2imp_binary():
            self.stdout.write(self.style.WARNING(f'mod2osis not found; using mod2imp for {module_name}.'))
            yield from self._iter_mod2imp_entries(module_name, module_root)
            return

        try:
            yield from self._iter_osis_entries(module_name, module_root)
        except CommandError:
            if not self._has_mod2imp_binary():
                raise
            self.stdout.write(self.style.WARNING(f'mod2osis failed for {module_name}, falling back to mod2imp.'))
            yield from self._iter_mod2imp_entries(module_name, module_root)

    def _import_source(self, config):
        source_id = str(config.get('id', '')).strip()
        module_name = str(config.get('module', '')).strip()
        display_name = str(config.get('label', source_id)).strip()
        language = str(config.get('language', 'en')).strip().lower()[:2]
        copyright_text = str(config.get('copyright_text', '')).strip()
        sort_order = int(config.get('sort_order', 100))
        import_format = str(config.get('import_format', 'auto')).strip().lower()

        if not source_id or not module_name:
            raise CommandError(f'Invalid SWORD source config: {config}')

        module_path = Path(str(config.get('path', '')).strip())
        if not module_path.is_absolute():
            module_path = Path(getattr(settings, 'BASE_DIR')).resolve() / module_path
        if not module_path.exists():
            raise CommandError(f'SWORD module path does not exist: {module_path}')

        self.stdout.write(f'Importing {source_id} from {module_path} ({module_name})')

        source, _ = SwordCommentarySource.objects.get_or_create(source_id=source_id)
        source.module_name = module_name
        source.display_name = display_name
        source.language = language
        source.copyright_text = copyright_text
        source.source_path = str(module_path)
        source.sort_order = sort_order
        source.is_enabled = True
        source.last_imported_at = timezone.now()
        source.save()

        entries = []
        for book_name, book_key, chapter, verse, text in self._iter_entries(module_name, module_path, import_format=import_format):
            entries.append(
                SwordCommentaryEntry(
                    source=source,
                    book=book_name,
                    book_key=book_key,
                    chapter=chapter,
                    verse=verse,
                    text=text,
                )
            )

        with transaction.atomic():
            SwordCommentaryEntry.objects.filter(source=source).delete()
            SwordCommentaryEntry.objects.bulk_create(entries, batch_size=1000)

        self.stdout.write(self.style.SUCCESS(f'Imported {len(entries)} entries for {source_id}.'))