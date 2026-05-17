import os

import pandas
from django.core.management import BaseCommand
from django.db import IntegrityError

from walkasjesus_app.models import Commandment, LawOfMessiah, LawOfMessiahDrawing, Lesson
from walkasjesus_website.settings import BASE_DIR


class Command(BaseCommand):
    help = 'Import Law of Messiah media from CSV.'

    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='The file name and path to read the data from.')

    def handle(self, *args, **options):
        file_path = options.get('source') or os.path.join(BASE_DIR, 'data', 'media', 'media_law_of_messiah.csv')
        df = pandas.read_csv(file_path, delimiter=';', na_filter=False)

        self.stdout.write(f'Adding {len(df.index)} shared media rows')

        for _, row in df.iterrows():
            law_id = str(row.get('lawofmessiah', '')).strip()
            step_id = str(row.get('step', '')).strip()
            lesson_id = str(row.get('lesson', '')).strip()

            if not any([law_id, step_id, lesson_id]):
                self.stdout.write(self.style.WARNING('Skipped shared media row without law, step, or lesson reference.'))
                continue

            media_type = str(row.get('media_type', '')).strip().lower() or LawOfMessiahDrawing.MEDIA_TYPE_DRAWING
            if media_type not in {choice[0] for choice in LawOfMessiahDrawing.MEDIA_TYPE_CHOICES}:
                self.stdout.write(self.style.WARNING(f'Skipped unsupported media_type={media_type} for row with law={law_id}, step={step_id}, lesson={lesson_id}'))
                continue

            law = None
            if law_id:
                law, _ = LawOfMessiah.objects.get_or_create(id=law_id)

            media = LawOfMessiahDrawing(
                law_of_messiah=law,
                commandment=Commandment.objects.filter(id=step_id).first() if step_id else None,
                lesson=Lesson.objects.filter(id=lesson_id).first() if lesson_id else None,
                media_type=media_type,
                title=row.get('media_title', ''),
                description=row.get('media_description_en', ''),
                target_audience=row.get('media_target_audience', 'any') or 'any',
                language=row.get('media_lang', 'any') or 'any',
                img_url=row.get('media_img_url', ''),
                url=row.get('media_url', ''),
                author=row.get('media_author', ''),
                is_public=str(row.get('media_public', '')).strip().lower() == 'yes',
            )
            self._save(media)

    def _save(self, model_object):
        try:
            model_object.save()
            self.stdout.write(f'Added {model_object}.')
        except IntegrityError:
            self.stdout.write(f'Skipped {model_object} as it already exists.')
        except Exception as ex:
            self.stdout.write(f'Failed inserting {model_object} with error {ex}.')
