import os
from pathlib import Path

from django.core.management import BaseCommand
import pandas
import yaml

from walkasjesus_app.models import Commandment, LawOfMessiah, LawOfMessiahDrawing, Lesson
from walkasjesus_website.settings import BASE_DIR


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='The file name and path to read the data from.')

    def handle(self, *args, **options):
        file_path = options.get('source') or os.path.join(BASE_DIR, 'data', 'media', 'media.csv')
        df = pandas.read_csv(file_path, delimiter=';', na_filter=False)

        step_to_law = self._step_to_law_mapping()
        inserted = 0
        skipped = 0
        for _, row in df.iterrows():
            if self._import_row(row, step_to_law):
                inserted += 1
            else:
                skipped += 1

        deduped = self._dedupe_shared_media()
        print(f'Imported shared media rows: {inserted}')
        print(f'Skipped shared media rows: {skipped}')
        print(f'Removed duplicate shared media rows: {deduped}')

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

    def _import_row(self, row, step_to_law):
        step_raw = str(row.get('step', '')).strip()
        law_raw = str(row.get('lawofmessiah', '')).strip()
        lesson_raw = str(row.get('lesson', '')).strip()

        commandment = Commandment.objects.filter(id=step_raw).first() if step_raw else None
        lesson = Lesson.objects.filter(id=lesson_raw).first() if lesson_raw else None

        if not commandment and lesson and lesson.commandment_id:
            commandment = lesson.commandment

        if not lesson and commandment:
            related_lessons = list(Lesson.objects.filter(commandment=commandment)[:2])
            if len(related_lessons) == 1:
                lesson = related_lessons[0]

        law = LawOfMessiah.objects.filter(id=law_raw).first() if law_raw else None
        if not law and commandment:
            mapped_law_id = step_to_law.get(str(commandment.id))
            if mapped_law_id:
                law = LawOfMessiah.objects.filter(id=mapped_law_id).first()
            else:
                related_laws = list(LawOfMessiah.objects.filter(related_steps=commandment)[:2])
                if len(related_laws) == 1:
                    law = related_laws[0]

        if not any([law, commandment, lesson]):
            return False

        media_type = str(row.get('media_type', '')).strip().lower() or LawOfMessiahDrawing.MEDIA_TYPE_DRAWING
        valid_media_types = {choice[0] for choice in LawOfMessiahDrawing.MEDIA_TYPE_CHOICES}
        if media_type not in valid_media_types:
            return False

        lookup = dict(
            law_of_messiah=law,
            commandment=commandment,
            lesson=lesson,
            media_type=media_type,
            title=row.get('media_title', ''),
            target_audience=(row.get('media_target_audience', 'any') or 'any'),
            language=(row.get('media_lang', 'en') or 'en'),
            img_url=row.get('media_img_url', ''),
            url=row.get('media_url', ''),
            author=row.get('media_author', ''),
        )
        defaults = {
            'description': row.get('media_description_en', ''),
            'is_public': str(row.get('media_public', '')).strip().lower() == 'yes',
        }

        queryset = LawOfMessiahDrawing.objects.filter(**lookup).order_by('id')
        existing = list(queryset[:2])
        if len(existing) > 1:
            queryset.exclude(id=existing[0].id).delete()

        if existing:
            media = existing[0]
            updated = False
            for field, value in defaults.items():
                if getattr(media, field) != value:
                    setattr(media, field, value)
                    updated = True
            if updated:
                media.save(update_fields=list(defaults.keys()))
            return False

        LawOfMessiahDrawing.objects.create(**lookup, **defaults)
        return True

    def _dedupe_shared_media(self):
        seen = {}
        to_delete_ids = []
        for media in LawOfMessiahDrawing.objects.order_by('id'):
            key = (
                media.law_of_messiah_id,
                media.commandment_id,
                media.lesson_id,
                str(media.media_type or '').strip().lower(),
                str(media.title or '').strip(),
                str(media.description or '').strip(),
                str(media.target_audience or '').strip(),
                str(media.language or '').strip(),
                str(media.img_url or '').strip(),
                str(media.url or '').strip(),
                str(media.author or '').strip(),
                bool(media.is_public),
            )
            if key in seen:
                to_delete_ids.append(media.id)
            else:
                seen[key] = media.id

        if not to_delete_ids:
            return 0

        deleted_count, _ = LawOfMessiahDrawing.objects.filter(id__in=to_delete_ids).delete()
        return deleted_count
