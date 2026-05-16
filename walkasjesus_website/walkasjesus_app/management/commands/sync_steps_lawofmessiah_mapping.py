from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from walkasjesus_app.models import LawOfMessiah, Commandment, LawOfMessiahDrawing


class Command(BaseCommand):
    help = "Sync steps_lawofmessiah_mapping.yaml to populate related_steps ManyToMany field"

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='data/biblereferences/steps_lawofmessiah_mapping.yaml',
            help='Path to steps_lawofmessiah_mapping.yaml',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing related_steps before syncing',
        )

    def handle(self, *args, **options):
        mapping_file = Path(options['file'])
        
        if not mapping_file.exists():
            self.stdout.write(self.style.ERROR(f"File not found: {mapping_file}"))
            return

        with open(mapping_file, 'r') as f:
            mappings = yaml.safe_load(f) or []

        if options['clear']:
            for law in LawOfMessiah.objects.all():
                law.related_steps.clear()
            self.stdout.write(self.style.SUCCESS("Cleared all related_steps"))

        created = 0
        updated = 0
        media_synced = 0
        skipped = 0
        
        for mapping in mappings:
            step_id = mapping.get('step_id')
            law_id = mapping.get('lawofmessiah_id')
            
            if not step_id or not law_id:
                skipped += 1
                continue
            
            try:
                step = Commandment.objects.get(pk=int(step_id))
                law = LawOfMessiah.objects.get(pk=law_id)
                
                if law.related_steps.filter(pk=step.pk).exists():
                    self.stdout.write(f"  ✓ Step {step_id} already linked to Law {law_id}")
                    updated += 1
                else:
                    law.related_steps.add(step)
                    self.stdout.write(self.style.SUCCESS(f"✓ Linked Step {step_id} to Law {law_id}"))
                    created += 1

                media_synced += self._sync_law_step_media(law, step)
            except (Commandment.DoesNotExist, LawOfMessiah.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f"✗ Skipped Step {step_id} → Law {law_id}: {str(e)}"))
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"\nSummary:"))
        self.stdout.write(f"  Created: {created}")
        self.stdout.write(f"  Updated: {updated}")
        self.stdout.write(f"  Step media synced: {media_synced}")
        self.stdout.write(f"  Skipped: {skipped}")

    def _sync_law_step_media(self, law, step):
        synced = 0
        media_map = {
            LawOfMessiahDrawing.MEDIA_TYPE_SONG: step.song_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_SUPERBOOK: step.superbook_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_HENKIESHOW: step.henkieshow_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_MOVIE: step.movie_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_SHORTMOVIE: step.shortmovie_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_WAJVIDEO: step.wajvideo_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_DRAWING: step.drawing_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_TESTIMONY: step.testimony_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_BLOG: step.blog_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_PICTURE: step.picture_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_SERMON: step.sermon_set.all(),
            LawOfMessiahDrawing.MEDIA_TYPE_BOOK: step.book_set.all(),
        }

        for media_type, items in media_map.items():
            for item in items:
                img_url = str(item.img_url or '').strip()
                url = str(item.url or '').strip()
                if not img_url and not url:
                    continue

                _, created = LawOfMessiahDrawing.objects.get_or_create(
                    law_of_messiah=law,
                    commandment=step,
                    media_type=media_type,
                    title=item.title or '',
                    description=item.description or '',
                    target_audience=item.target_audience,
                    language=item.language,
                    img_url=img_url,
                    url=url,
                    author=item.author or '',
                    defaults={
                        'is_public': item.is_public,
                    },
                )
                if created:
                    synced += 1

        if synced:
            self.stdout.write(self.style.SUCCESS(f"  + Synced {synced} media items from Step {step.id} to Law {law.id}"))

        return synced
