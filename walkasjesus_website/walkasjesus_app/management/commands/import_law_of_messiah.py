import os
import re

from django.core.management import BaseCommand
from import_tool.bible_reference import BibleReference as ImportedBibleReference
import yaml

from walkasjesus_app.models import Commandment, LawOfMessiah, LawOfMessiahBibleReference
from walkasjesus_website.settings import BASE_DIR


class Command(BaseCommand):
    help = 'Import Law of Messiah commandments from reviewed expanded YAML file.'

    NT_PREFIXES = {
        'AA', 'AB', 'AC', 'AD', 'AE', 'AF', 'AG',
        'BA', 'BB', 'BC', 'BD', 'BE', 'BF', 'BG',
        'CA', 'CB', 'CC', 'CD', 'CE', 'CF', 'CG',
        'DA', 'DB', 'DC', 'DD', 'DE', 'DF', 'DG',
        'EA', 'EB', 'EC', 'ED', 'EE', 'EF', 'EG',
        'FA', 'FB', 'FC', 'FD', 'FE', 'FF', 'FG',
        'GA', 'GB', 'GC', 'GD', 'GE', 'GF',
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--source',
            type=str,
            default=os.path.join(
                BASE_DIR,
                'data',
                'lawofmessiah',
                'filter_output',
                'collected_ids_titles.yaml',
            ),
            help='Path to collected_ids_titles.yaml',
        )

    def handle(self, *args, **options):
        source = self._resolve_source(options['source'])
        items = self._load_items(source)
        items = [item for item in items if self._is_law_of_messiah_item(item)]

        self.stdout.write(f'Importing {len(items)} Law of Messiah records')
        for item in items:
            self._upsert_item(item)

    def _resolve_source(self, source):
        if os.path.exists(source):
            return source

        legacy_name = 'collected_ids_titles.yaml'
        fallback_name = 'filtered_commandments.yaml'
        if os.path.basename(source) == legacy_name:
            fallback_source = os.path.join(os.path.dirname(source), fallback_name)
            if os.path.exists(fallback_source):
                self.stdout.write(
                    self.style.WARNING(
                        f'Source file not found: {source}. Falling back to: {fallback_source}'
                    )
                )
                return fallback_source

        raise FileNotFoundError(f'Source YAML not found: {source}')

    def _load_items(self, source):
        with open(source, 'r', encoding='utf-8') as file_handle:
            parsed = yaml.safe_load(file_handle) or []
        if isinstance(parsed, list):
            return parsed
        return []

    def _is_law_of_messiah_item(self, item):
        item_id = str((item or {}).get('id', '')).strip().upper()
        return bool(item_id) and not item_id.startswith('STEP')

    def _upsert_item(self, item):
        item_id = str(item.get('id', '')).strip()
        if not item_id:
            return

        commandment_type = self._map_commandment_type(item.get('commandment_type'))
        ncla_data = self._map_ncla(item.get('ncla'))
        ncla_deviation = self._map_bool(item.get('ncla_deviation', False))
        if commandment_type == LawOfMessiah.COMMANDMENT_TYPE_NEGATIVE:
            # Negative commandments are intentionally excluded from context/situation filtering.
            ncla_data = []
            ncla_deviation = False

        commandment_form = self._map_commandment_form(item.get('commandment_form'))
        source_dataset = self._map_source_dataset(item.get('source_dataset'), item_id)

        defaults = {
            'source_dataset': source_dataset,
            'title': item.get('title', '') or '',
            'commandment': item.get('commandment', '') or '',
            'commandment_subtitles': self._map_string_list(item.get('commandment_subtitles')),
            'commandment_type': commandment_type,
            'commandment_form': commandment_form,
            'category': item.get('category', '') or '',
            'is_unique': self._map_bool(item.get('unique', False)),
            'commentary_rudolph': item.get('commentary_rudolph', '') or '',
            'commentary_juster': item.get('commentary_juster', '') or '',
            'classical_commentators': item.get('classical_commentators', '') or '',
            'commandments_related_ot': item.get('commandments_related_ot') or [],
            'commandments_related_nt': item.get('commandments_related_nt') or [],
            'related_lawofmessiah': self._map_related_lawofmessiah(item),
            'maimonides': item.get('maimonides') or [],
            'meir': item.get('meir') or [],
            'chinuch': item.get('chinuch') or [],
            'ncla': ncla_data,
            'ncla_deviation': ncla_deviation,
            'classical_commandment': self._map_bool(item.get('classical_commandment', False)),
            'source': item.get('source', '') or '',
            'copyright': item.get('copyright', '') or '',
        }

        obj, created = LawOfMessiah.objects.update_or_create(id=item_id, defaults=defaults)
        self._sync_bible_references(obj, item.get('bible_references') or {})
        self._sync_related_steps(obj, item.get('related_steps') or [])
        action = 'Added' if created else 'Updated'
        self.stdout.write(f'{action} {obj.id}')

    def _map_source_dataset(self, value, item_id):
        normalized = str(value or '').strip().lower()
        if normalized == LawOfMessiah.SOURCE_DATASET_NT:
            return LawOfMessiah.SOURCE_DATASET_NT
        if normalized == LawOfMessiah.SOURCE_DATASET_OT:
            return LawOfMessiah.SOURCE_DATASET_OT

        if self._is_nt_id(item_id):
            return LawOfMessiah.SOURCE_DATASET_NT
        return LawOfMessiah.SOURCE_DATASET_OT

    def _is_nt_id(self, item_id):
        normalized = str(item_id or '').strip().upper()
        match = re.match(r'^([A-Z]+)\d+$', normalized)
        if not match:
            return False
        return match.group(1) in self.NT_PREFIXES

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
        """Store NCLA as structured list of groups: [{"group": "...", "codes": ["JMm", ...]}]"""
        valid_codes = {code for code, _ in LawOfMessiah.NCLA_CHOICES}
        groups = []
        if isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    raw_codes = str(entry.get('code', '') or '').split()
                    group_name = str(entry.get('group', 'All') or 'All').strip()
                elif isinstance(entry, str):
                    raw_codes = entry.split()
                    group_name = 'All'
                else:
                    raw_codes = str(entry or '').split()
                    group_name = 'All'
                filtered = sorted(set(c for c in raw_codes if c in valid_codes))
                if filtered:
                    groups.append({'group': group_name, 'codes': filtered})
        elif isinstance(value, dict):
            raw_codes = str(value.get('code', '') or '').split()
            group_name = str(value.get('group', 'All') or 'All').strip()
            filtered = sorted(set(c for c in raw_codes if c in valid_codes))
            if filtered:
                groups.append({'group': group_name, 'codes': filtered})
        elif value:
            raw_codes = str(value).split()
            filtered = sorted(set(c for c in raw_codes if c in valid_codes))
            if filtered:
                groups.append({'group': 'All', 'codes': filtered})
        return groups

    def _map_string_list(self, value):
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        return [text]

    def _map_bool(self, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        normalized = str(value).strip().lower()
        return normalized in {'1', 'true', 'yes', 'y', 'on'}

    def _map_related_lawofmessiah(self, item):
        raw_items = item.get('related_lawofmessiah')
        if raw_items is None:
            # Backward compatibility with older YAML variants.
            raw_items = []
            raw_items.extend(item.get('commandments_related_ot') or [])
            raw_items.extend(item.get('commandments_related_nt') or [])

        if not raw_items:
            return []
        if not isinstance(raw_items, list):
            raw_items = [raw_items]

        dedup = {}
        for entry in raw_items:
            if isinstance(entry, dict):
                raw_id = str(entry.get('id', '')).strip().upper()
                title = str(entry.get('title', '')).strip()
            else:
                raw_id = str(entry).strip().upper()
                title = ''
            if not raw_id:
                continue
            if raw_id not in dedup:
                dedup[raw_id] = {'id': raw_id, 'title': title}

        return [dedup[item_id] for item_id in sorted(dedup.keys())]

    def _sync_related_steps(self, law_of_messiah, related_steps):
        step_numbers = []
        unresolved = []

        if not isinstance(related_steps, list):
            related_steps = [related_steps]

        for related in related_steps:
            if isinstance(related, dict):
                raw_id = str(related.get('id', '') or related.get('step', '')).strip().upper()
            else:
                raw_id = str(related).strip().upper()
            if not raw_id:
                continue

            match = re.match(r'^STEP(\d+)$', raw_id)
            if not match:
                match = re.match(r'^(\d+)$', raw_id)
            if not match:
                continue

            step_number = int(match.group(1))
            step_numbers.append(step_number)

        commandment_ids = set(Commandment.objects.filter(id__in=step_numbers).values_list('id', flat=True))
        unresolved = [step for step in sorted(set(step_numbers)) if step not in commandment_ids]
        law_of_messiah.related_steps.set(commandment_ids)

        if unresolved:
            unresolved_display = ', '.join(str(step) for step in unresolved)
            self.stdout.write(self.style.WARNING(f'Unresolved related steps for {law_of_messiah.id}: {unresolved_display}'))

    def _sync_bible_references(self, law_of_messiah, bible_references):
        LawOfMessiahBibleReference.objects.filter(law_of_messiah=law_of_messiah).delete()
        if not isinstance(bible_references, dict):
            return

        valid_types = {
            LawOfMessiahBibleReference.TYPE_KEY_NT,
            LawOfMessiahBibleReference.TYPE_KEY_OT,
            LawOfMessiahBibleReference.TYPE_SUPPORTIVE_NT,
            LawOfMessiahBibleReference.TYPE_SUPPORTIVE_OT,
        }
        aliases = {
            'nt_scriptures': LawOfMessiahBibleReference.TYPE_KEY_NT,
            'ot_scriptures': LawOfMessiahBibleReference.TYPE_KEY_OT,
        }

        for reference_type, references in bible_references.items():
            reference_type = aliases.get(reference_type, reference_type)
            if reference_type not in valid_types:
                continue
            if not references:
                continue

            if not isinstance(references, list):
                references = [references]

            for order, reference in enumerate(references):
                if isinstance(reference, dict):
                    ref_text = str(reference.get('read', '') or reference.get('title', '')).strip()
                else:
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
