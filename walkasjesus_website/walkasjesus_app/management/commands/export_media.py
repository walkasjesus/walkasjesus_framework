import csv
from pathlib import Path

from django.core.management import BaseCommand
from pandas import DataFrame
import yaml

from walkasjesus_app.models import LawOfMessiah, LawOfMessiahDrawing, Lesson


class Command(BaseCommand):
    """ Export the media in the database to a csv file. """
    def __init__(self):
        super().__init__()
        columns = ['step',
                   'lawofmessiah',
                   'lesson',
                   'media_author',
                   'media_title',
                   'media_description_en',
                   'media_target_audience',
                   'media_lang',
                   'media_type',
                   'media_public',
                   'media_img_url',
                   'media_url'
                   ]

        self.data_frame = DataFrame(columns=columns)
        self.last_row_index = 0

    def add_arguments(self, parser):
        parser.add_argument('destination', type=str, help='The file name and path to write the export to.')

    def handle(self, *args, **options):
        destination_csv = options['destination']
        step_to_law = self._step_to_law_mapping()
        self.line_terminator = self._detect_lineterminator(destination_csv)
        existing_order = self._existing_row_order(destination_csv)
        existing_keys = self._existing_row_keys(destination_csv)

        seen = set()
        export_rows = []
        rows = LawOfMessiahDrawing.objects.select_related('law_of_messiah', 'commandment', 'lesson').order_by('id')
        for media in rows:
            step_id, law_id, lesson_id = self._resolve_relation_ids(media, step_to_law)
            row_key = (
                str(step_id or '').strip(),
                str(law_id or '').strip(),
                str(lesson_id or '').strip(),
                str(media.author or '').strip(),
                str(media.title or '').strip(),
                str(media.description or '').strip(),
                str(media.target_audience or '').strip(),
                str(media.language or '').strip(),
                str(media.media_type or '').strip().lower(),
                'yes' if media.is_public else 'no',
                str(media.img_url or '').strip(),
                str(media.url or '').strip(),
            )
            if row_key in seen:
                continue
            seen.add(row_key)

            export_rows.append((row_key, {
                'step': step_id,
                'lawofmessiah': law_id,
                'lesson': lesson_id,
                'media_author': media.author,
                'media_title': media.title,
                'media_description_en': media.description,
                'media_target_audience': media.target_audience,
                'media_lang': media.language,
                'media_type': media.media_type,
                'media_public': 'yes' if media.is_public else 'no',
                'media_img_url': media.img_url,
                'media_url': media.url,
            }))

        export_rows.sort(key=lambda item: self._sort_key(item[0], existing_order))

        for _, row in export_rows:
            self.write_field('step', row['step'])
            self.write_field('lawofmessiah', row['lawofmessiah'])
            self.write_field('lesson', row['lesson'])
            self.write_field('media_author', row['media_author'])
            self.write_field('media_title', row['media_title'])
            self.write_field('media_description_en', row['media_description_en'])
            self.write_field('media_target_audience', row['media_target_audience'])
            self.write_field('media_lang', row['media_lang'])
            self.write_field('media_type', row['media_type'])
            self.write_field('media_public', row['media_public'])
            self.write_field('media_img_url', row['media_img_url'])
            self.write_field('media_url', row['media_url'])
            self.start_new_row()

        export_keys = [row_key for row_key, _ in export_rows]
        if self._is_append_only(existing_keys, export_keys):
            self._append_new_rows(destination_csv, export_rows[len(existing_keys):])
            print(f'Written export to {destination_csv}')
            return

        self.data_frame.to_csv(
            destination_csv,
            index=False,
            sep=';',
            lineterminator=self.line_terminator,
        )
        print(f'Written export to {destination_csv}')

    def _detect_lineterminator(self, destination_csv):
        try:
            with open(destination_csv, 'rb') as handle:
                sample = handle.read(4096)
            if b'\r\n' in sample:
                return '\r\n'
        except FileNotFoundError:
            pass
        return '\n'

    def _step_to_law_mapping(self):
        mapping_file = Path(__file__).resolve().parents[3] / 'data' / 'biblereferences' / 'steps_lawofmessiah_mapping.yaml'
        if not mapping_file.exists():
            return {}
        try:
            with open(mapping_file, 'r', encoding='utf-8') as handle:
                rows = yaml.safe_load(handle) or []
        except Exception:
            return {}

        mapping = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            step_id = str(row.get('step_id', '')).strip()
            law_id = str(row.get('lawofmessiah_id', '')).strip()
            if step_id and law_id:
                mapping[step_id] = law_id
        return mapping

    def _existing_row_order(self, destination_csv):
        order = {}
        try:
            with open(destination_csv, 'r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle, delimiter=';')
                for index, row in enumerate(reader):
                    key = self._row_key_from_dict(row)
                    if key not in order:
                        order[key] = index
        except FileNotFoundError:
            return {}
        except Exception:
            return {}
        return order

    def _existing_row_keys(self, destination_csv):
        keys = []
        try:
            with open(destination_csv, 'r', encoding='utf-8', newline='') as handle:
                reader = csv.DictReader(handle, delimiter=';')
                for row in reader:
                    keys.append(self._row_key_from_dict(row))
        except FileNotFoundError:
            return []
        except Exception:
            return []
        return keys

    def _is_append_only(self, existing_keys, export_keys):
        if not existing_keys:
            return False
        if len(export_keys) < len(existing_keys):
            return False
        return export_keys[:len(existing_keys)] == existing_keys

    def _append_new_rows(self, destination_csv, new_rows):
        if not new_rows:
            return

        columns = [
            'step',
            'lawofmessiah',
            'lesson',
            'media_author',
            'media_title',
            'media_description_en',
            'media_target_audience',
            'media_lang',
            'media_type',
            'media_public',
            'media_img_url',
            'media_url',
        ]

        with open(destination_csv, 'a', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle, delimiter=';', lineterminator='\n')
            for _, row in new_rows:
                writer.writerow([
                    self._normalize_field(row.get(column, ''))
                    for column in columns
                ])

    def _normalize_field(self, value):
        if value is None:
            return ''
        text = str(value)
        return text.replace('\r\n', '\n').replace('\r', '\n')

    def _row_key_from_dict(self, row):
        return (
            str((row or {}).get('step', '') or '').strip(),
            str((row or {}).get('lawofmessiah', '') or '').strip(),
            str((row or {}).get('lesson', '') or '').strip(),
            str((row or {}).get('media_author', '') or '').strip(),
            str((row or {}).get('media_title', '') or '').strip(),
            str((row or {}).get('media_description_en', '') or '').strip(),
            str((row or {}).get('media_target_audience', '') or '').strip(),
            str((row or {}).get('media_lang', '') or '').strip(),
            str((row or {}).get('media_type', '') or '').strip().lower(),
            str((row or {}).get('media_public', '') or '').strip().lower(),
            str((row or {}).get('media_img_url', '') or '').strip(),
            str((row or {}).get('media_url', '') or '').strip(),
        )

    def _sort_key(self, row_key, existing_order):
        if row_key in existing_order:
            return (0, existing_order[row_key])
        return (1,) + row_key

    def _resolve_relation_ids(self, media, step_to_law):
        step_id = media.commandment_id
        lesson_id = media.lesson_id
        law_id = media.law_of_messiah_id

        if not step_id and media.lesson and media.lesson.commandment_id:
            step_id = media.lesson.commandment_id

        if not lesson_id and step_id:
            linked_lessons = list(Lesson.objects.filter(commandment_id=step_id).values_list('id', flat=True)[:2])
            if len(linked_lessons) == 1:
                lesson_id = linked_lessons[0]

        if not law_id and step_id:
            mapped = step_to_law.get(str(step_id))
            if mapped:
                law_id = mapped
            else:
                related_laws = list(LawOfMessiah.objects.filter(related_steps__id=step_id).values_list('id', flat=True)[:2])
                if len(related_laws) == 1:
                    law_id = related_laws[0]

        return step_id or '', law_id or '', lesson_id or ''

    def write_field(self, column_name, value):
        if isinstance(value, str):
            value = value.replace('\r\n', '\n').replace('\r', '\n')
            if self.line_terminator == '\r\n':
                value = value.replace('\n', '\r\n')
        self.data_frame.at[self.last_row_index, column_name] = value

    def start_new_row(self):
        self.last_row_index += 1
