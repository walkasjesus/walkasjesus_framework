import os
import re

from django.core.management import BaseCommand
from import_tool import LawOfMessiahImporter
from import_tool.bible_reference import BibleReference as ImportedBibleReference

from walkasjesus_app.models import LawOfMessiah, LawOfMessiahBibleReference
from walkasjesus_website.settings import BASE_DIR


class Command(BaseCommand):
    help = 'Import Law of Messiah commandments from OT + NT YAML files.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ot-source',
            type=str,
            default=os.path.join(BASE_DIR, 'data', 'lawofmessiah', 'Law_of_Messiah_ot.yaml'),
            help='Path to Law_of_Messiah_ot.yaml',
        )
        parser.add_argument(
            '--nt-source',
            type=str,
            default=os.path.join(BASE_DIR, 'data', 'lawofmessiah', 'Law_of_Messiah_nt.yaml'),
            help='Path to Law_of_Messiah_nt.yaml',
        )

    def handle(self, *args, **options):
        ot_source = options['ot_source']
        nt_source = options['nt_source']

        importer = LawOfMessiahImporter()
        items = importer.load(old_testament_file=ot_source, new_testament_file=nt_source)

        self.stdout.write(f'Importing {len(items)} Law of Messiah records')
        for item in items:
            self._upsert_item(item)

    def _upsert_item(self, item):
        item_id = str(item.get('id', '')).strip()
        if not item_id:
            return

        commandment_type = self._map_commandment_type(item.get('commandment_type'))
        commandment_form = self._map_commandment_form(item.get('commandment_form'))
        source_dataset = self._map_source_dataset(item.get('source_dataset'))

        defaults = {
            'source_dataset': source_dataset,
            'title': item.get('title', '') or '',
            'commandment': item.get('commandment', '') or '',
            'commandment_type': commandment_type,
            'commandment_form': commandment_form,
            'category': item.get('category', '') or '',
            'commentary_rudolph': item.get('commentary_rudolph', '') or '',
            'commentary_juster': item.get('commentary_juster', '') or '',
            'classical_commentators': item.get('classical_commentators', '') or '',
            'commandments_related_ot': item.get('commandments_related_ot') or [],
            'commandments_related_nt': item.get('commandments_related_nt') or [],
            'maimonides': item.get('maimonides') or [],
            'meir': item.get('meir') or [],
            'chinuch': item.get('chinuch') or [],
            'ncla': self._map_ncla(item.get('ncla')),
            'ncla_deviation': bool(item.get('ncla_deviation', False)),
            'classical_commandment': bool(item.get('classical_commandment', False)),
            'source': item.get('source', '') or '',
            'copyright': item.get('copyright', '') or '',
        }

        obj, created = LawOfMessiah.objects.update_or_create(id=item_id, defaults=defaults)
        self._sync_bible_references(obj, item.get('bible_references') or {})
        action = 'Added' if created else 'Updated'
        self.stdout.write(f'{action} {obj.id}')

    def _map_source_dataset(self, value):
        normalized = str(value or '').strip().lower()
        if normalized == LawOfMessiah.SOURCE_DATASET_NT:
            return LawOfMessiah.SOURCE_DATASET_NT
        return LawOfMessiah.SOURCE_DATASET_OT

    def _map_commandment_type(self, value):
        normalized = str(value or '').strip().lower().replace('&', 'and')
        if 'positive' in normalized and 'negative' in normalized:
            return LawOfMessiah.COMMANDMENT_TYPE_BOTH
        if normalized == 'negative':
            return LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE
        return LawOfMessiah.COMMANDMENT_TYPE_POSITIVE

    def _map_commandment_form(self, value):
        normalized = str(value or '').strip().lower()
        if normalized in ('', '-', 'none', 'null'):
            return LawOfMessiah.COMMANDMENT_FORM_EMPTY
        if normalized in ('implied', 'implicit'):
            return LawOfMessiah.COMMANDMENT_FORM_IMPLIED
        return LawOfMessiah.COMMANDMENT_FORM_EXPLICIT

    def _map_ncla(self, value):
        if isinstance(value, list):
            candidates = value
        else:
            candidates = str(value or '').split()

        valid_codes = {code for code, _ in LawOfMessiah.NCLA_CHOICES}
        filtered = [code for code in candidates if code in valid_codes]
        return sorted(set(filtered))

    def _sync_bible_references(self, law_of_messiah, bible_references):
        LawOfMessiahBibleReference.objects.filter(law_of_messiah=law_of_messiah).delete()
        valid_types = {
            LawOfMessiahBibleReference.TYPE_KEY_NT,
            LawOfMessiahBibleReference.TYPE_KEY_OT,
            LawOfMessiahBibleReference.TYPE_SUPPORTIVE_NT,
            LawOfMessiahBibleReference.TYPE_SUPPORTIVE_OT,
        }

        for reference_type, references in bible_references.items():
            if reference_type not in valid_types:
                continue
            if not references:
                continue

            if not isinstance(references, list):
                references = [references]

            for order, reference in enumerate(references):
                ref_text = str(reference).strip()
                if not ref_text:
                    continue

                parsed_entries = self._expand_and_parse_references(ref_text)
                if not parsed_entries:
                    self.stdout.write(f'Skipped unparseable reference for {law_of_messiah.id}: {ref_text}')
                    continue

                for parsed in parsed_entries:
                    LawOfMessiahBibleReference.objects.create(
                        law_of_messiah=law_of_messiah,
                        reference_type=reference_type,
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
            'philippians': 'Php',
            'colossians': 'Col',
            '1 thessalonians': '1TH',
            '2 thessalonians': '2TH',
            '1 timothy': '1TI',
            '2 timothy': '2TI',
            'titus': 'Tit',
            'philemon': 'Phm',
            'hebrews': 'Heb',
            'james': 'Jas',
            '1 peter': '1PE',
            '2 peter': '2PE',
            '1 john': '1JN',
            '2 john': '2JN',
            '3 john': '3JN',
            'jude': 'Jud',
            'revelation': 'Rev',
        }

        return mapping.get(normalized, book)
