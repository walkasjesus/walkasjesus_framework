"""
Importer for Maimonides commandments from YAML source.
Usage: python manage.py import_maimonides
"""
import logging
import os
import re
import yaml
from django.core.management.base import BaseCommand
from import_tool.bible_reference import BibleReference as ImportedBibleReference

from walkasjesus_app.models import Maimonides, MaimonidesBibleReference

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Import Maimonides commandments from YAML file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default='data/lawofmessiah/volume_1_2_output/output_maimonides.yaml',
            help='Path to Maimonides YAML file',
        )

    def handle(self, *args, **options):
        source_path = options['source']
        if not os.path.exists(source_path):
            self.stdout.write(self.style.ERROR(f'File not found: {source_path}'))
            return

        self.stdout.write(self.style.SUCCESS(f'Importing Maimonides from {source_path}'))

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error reading YAML: {e}'))
            return

        commandments = data.get('commandments', [])
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for item in commandments:
            cmd_id = str(item.get('id', '')).strip()
            cmd_type = self._map_commandment_type(item.get('commandment_type', 'positive'))
            commandment_text = str(item.get('commandment', '')).strip()
            meir = self._normalize_string_list(item.get('meir', []))
            chinuch = self._normalize_string_list(item.get('chinuch', []))
            rudolph = self._normalize_string_list(item.get('rudolph', []))
            scriptures = self._normalize_string_list(item.get('scriptures', []))
            meir_scriptures = self._normalize_scripture_details(item.get('meir_scriptures', []))
            chinuch_scriptures = self._normalize_scripture_details(item.get('chinuch_scriptures', []))

            if not cmd_id:
                skipped_count += 1
                continue

            obj, created = Maimonides.objects.update_or_create(
                id=cmd_id,
                defaults={
                    'commandment_type': cmd_type,
                    'commandment': commandment_text,
                    'meir': meir,
                    'chinuch': chinuch,
                    'rudolph': rudolph,
                    'scriptures': scriptures,
                    'meir_scriptures': meir_scriptures,
                    'chinuch_scriptures': chinuch_scriptures,
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

            self._sync_bible_references(
                obj,
                scriptures=scriptures,
                meir_scriptures=meir_scriptures,
                chinuch_scriptures=chinuch_scriptures,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Import complete: {created_count} created, {updated_count} updated, {skipped_count} skipped'
            )
        )

    def _map_commandment_type(self, value):
        """Map commandment type to model choice."""
        normalized = str(value or '').lower().strip()
        if 'negative' in normalized:
            return Maimonides.COMMANDMENT_TYPE_NEGATIVE
        return Maimonides.COMMANDMENT_TYPE_POSITIVE

    def _normalize_string_list(self, value):
        if not isinstance(value, list):
            value = [value] if value else []

        normalized = []
        seen = set()
        for item in value:
            text = str(item or '').strip()
            if text and text not in seen:
                normalized.append(text)
                seen.add(text)
        return normalized

    def _normalize_scripture_details(self, value):
        if not isinstance(value, list):
            return []

        normalized = []
        for item in value:
            if not isinstance(item, dict):
                continue

            item_id = str(item.get('id', '')).strip()
            scriptures = self._normalize_string_list(item.get('scriptures', []))
            if not item_id or not scriptures:
                continue

            normalized.append({
                'id': item_id,
                'scriptures': scriptures,
            })

        return normalized

    def _sync_bible_references(self, maimonides, scriptures, meir_scriptures, chinuch_scriptures):
        MaimonidesBibleReference.objects.filter(maimonides=maimonides).delete()

        for ref_text in scriptures or []:
            self._create_reference_rows(
                maimonides=maimonides,
                reference_type=MaimonidesBibleReference.TYPE_MAIMONIDES,
                source_code='',
                reference_text=ref_text,
            )

        for item in meir_scriptures or []:
            source_code = str(item.get('id', '')).strip()
            for ref_text in item.get('scriptures', []):
                self._create_reference_rows(
                    maimonides=maimonides,
                    reference_type=MaimonidesBibleReference.TYPE_MEIR,
                    source_code=source_code,
                    reference_text=ref_text,
                )

        for item in chinuch_scriptures or []:
            source_code = str(item.get('id', '')).strip()
            for ref_text in item.get('scriptures', []):
                self._create_reference_rows(
                    maimonides=maimonides,
                    reference_type=MaimonidesBibleReference.TYPE_CHINUCH,
                    source_code=source_code,
                    reference_text=ref_text,
                )

    def _create_reference_rows(self, maimonides, reference_type, source_code, reference_text):
        parsed_entries = self._expand_and_parse_references(reference_text)
        if not parsed_entries:
            self.stdout.write(f'Skipped unparseable reference for {maimonides.id}: {reference_text}')
            return

        for parsed in parsed_entries:
            MaimonidesBibleReference.objects.create(
                maimonides=maimonides,
                reference_type=reference_type,
                source_code=source_code,
                book=parsed['book'],
                begin_chapter=parsed['begin_chapter'],
                begin_verse=parsed['begin_verse'],
                end_chapter=parsed['end_chapter'],
                end_verse=parsed['end_verse'],
            )

    def _expand_and_parse_references(self, reference_text):
        expanded = self._expand_compact_reference_list(reference_text)
        parsed = []
        for candidate in expanded:
            result = self._parse_single_reference(candidate)
            if result:
                parsed.append(result)
        return parsed

    def _expand_compact_reference_list(self, reference_text):
        cleaned = self._cleanup_reference_text(reference_text)
        match = re.match(r'^\s*([1-3]?\s*[A-Za-z][A-Za-z\s]+?)\s+(.+)$', cleaned)
        if not match or ',' not in cleaned:
            return [cleaned]

        book = self._normalize_book_name(match.group(1).strip())
        tail = match.group(2).strip()
        parts = [part.strip() for part in tail.split(',') if part.strip()]
        if not parts:
            return [cleaned]

        expanded = []
        current_chapter = None
        for part in parts:
            part = part.replace('–', '-').replace('—', '-')

            if re.match(r'^\d+:\d+(-\d+:\d+)?$', part) or re.match(r'^\d+:\d+-\d+$', part):
                current_chapter = int(part.split(':', 1)[0])
                expanded.append(f'{book} {part}')
                continue

            if re.match(r'^\d+-\d+$', part) and current_chapter is not None:
                expanded.append(f'{book} {current_chapter}:{part}')
                continue

            if re.match(r'^\d+$', part) and current_chapter is not None:
                expanded.append(f'{book} {current_chapter}:{part}')
                continue

            if re.search(r'[A-Za-z]', part):
                expanded.append(self._cleanup_reference_text(part))
            else:
                expanded.append(f'{book} {part}')

        return expanded or [cleaned]

    def _parse_single_reference(self, reference_text):
        candidate = self._cleanup_reference_text(reference_text)
        candidate = self._normalize_reference_format(candidate)
        candidate = self._normalize_book_prefix(candidate)

        try:
            parsed = ImportedBibleReference.create_from_string(candidate)
        except Exception:
            return None

        return {
            'book': parsed.book.name,
            'begin_chapter': parsed.start_chapter,
            'begin_verse': parsed.start_verse,
            'end_chapter': parsed.end_chapter,
            'end_verse': parsed.end_verse,
        }

    def _cleanup_reference_text(self, text):
        cleaned = str(text or '').strip()
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    def _normalize_reference_format(self, text):
        return re.sub(r'(\d+)\.(\d+)', r'\1:\2', text)

    def _normalize_book_prefix(self, text):
        match = re.match(r'^\s*([1-3]?\s*[A-Za-z][A-Za-z\s]+?)\s+(.+)$', text)
        if not match:
            return text
        book = self._normalize_book_name(match.group(1).strip())
        rest = match.group(2).strip()
        return f'{book} {rest}'

    def _normalize_book_name(self, book):
        normalized = ' '.join(book.lower().split())
        mapping = {
            'genesis': 'Gen',
            'exodus': 'Ex',
            'leviticus': 'Lev',
            'numbers': 'Num',
            'deuteronomy': 'Deut',
            'joshua': 'Jos',
            'judges': 'Jdg',
            'ruth': 'Ruth',
            '1 samuel': '1SA',
            '2 samuel': '2SA',
            '1 kings': '1KI',
            '2 kings': '2KI',
            '1 chronicles': '1CH',
            '2 chronicles': '2CH',
            'ezra': 'Ezra',
            'nehemiah': 'Neh',
            'esther': 'Est',
            'job': 'Job',
            'psalm': 'Psa',
            'psalms': 'Psa',
            'proverbs': 'Pro',
            'ecclesiastes': 'Ecc',
            'song of solomon': 'Sng',
            'isaiah': 'Isa',
            'jeremiah': 'Jer',
            'lamentations': 'Lam',
            'ezekiel': 'Eze',
            'daniel': 'Dan',
            'hosea': 'Hos',
            'joel': 'Joel',
            'amos': 'Amo',
            'obadiah': 'Oba',
            'jonah': 'Jon',
            'micah': 'Mic',
            'nahum': 'Nah',
            'habakkuk': 'Hab',
            'zephaniah': 'Zep',
            'haggai': 'Hag',
            'zechariah': 'Zec',
            'malachi': 'Mal',
            'matthew': 'Matt',
            'mark': 'Mrk',
            'luke': 'Luk',
            'john': 'Joh',
            'acts': 'Act',
            'romans': 'Rom',
            '1 corinthians': '1CO',
            '2 corinthians': '2CO',
            'galatians': 'Gal',
            'ephesians': 'Eph',
            'philippians': 'Phl',
            'colossians': 'Col',
            '1 thessalonians': '1TH',
            '2 thessalonians': '2TH',
            '1 timothy': '1TI',
            '2 timothy': '2TI',
            'titus': 'Tit',
            'philemon': 'Phm',
            'hebrews': 'Heb',
            'james': 'Jam',
            '1 peter': '1PE',
            '2 peter': '2PE',
            '1 john': '1JO',
            '2 john': '2JO',
            '3 john': '3JO',
            'jude': 'Jud',
            'revelation': 'Rev',
        }
        return mapping.get(normalized, book)
