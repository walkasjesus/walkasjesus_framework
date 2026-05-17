from django.core.management import BaseCommand

from walkasjesus_app.media_image_utils import normalize_media_relative_path, resolve_media_relative_path
from walkasjesus_app.models.commandment_media import Drawing
from walkasjesus_app.models.lesson_media import LessonDrawing
from walkasjesus_app.models.law_of_messiah_media import LawOfMessiahDrawing
from walkasjesus_website.settings import MEDIA_URL


class Command(BaseCommand):
    help = 'Repair stale img_url values by resolving them against files present in MEDIA_ROOT.'

    def handle(self, *args, **options):
        repaired = 0
        unresolved = 0
        deduped = 0

        for model in (Drawing, LessonDrawing, LawOfMessiahDrawing):
            model_repaired = 0
            model_unresolved = 0
            model_deduped = 0
            queryset = model.objects.exclude(img_url__isnull=True).exclude(img_url='')
            for instance in queryset.iterator():
                original_img_url = str(instance.img_url or '').strip()
                resolved_path = resolve_media_relative_path(original_img_url)
                if not resolved_path:
                    model_unresolved += 1
                    continue

                normalized_original = normalize_media_relative_path(original_img_url)
                if normalized_original == resolved_path:
                    continue

                replacement_img_url = f"{MEDIA_URL}{resolved_path}"
                conflict = self._find_conflict(instance, replacement_img_url)
                if conflict:
                    instance.delete()
                    model_deduped += 1
                    continue

                instance.img_url = replacement_img_url
                instance.save(update_fields=['img_url'])
                model_repaired += 1

            repaired += model_repaired
            unresolved += model_unresolved
            deduped += model_deduped
            self.stdout.write(
                f"{model._meta.label}: repaired={model_repaired} deduped={model_deduped} unresolved={model_unresolved}"
            )

        self.stdout.write(self.style.SUCCESS(f"Total repaired img_url values: {repaired}"))
        self.stdout.write(self.style.SUCCESS(f"Total deduped img_url rows: {deduped}"))
        self.stdout.write(f"Total unresolved img_url values: {unresolved}")

    def _find_conflict(self, instance, replacement_img_url):
        unique_together = getattr(instance._meta, 'unique_together', ()) or ()
        if not unique_together:
            return None

        conflict_lookup = {}
        for field_name in unique_together[0]:
            if field_name == 'img_url':
                conflict_lookup[field_name] = replacement_img_url
            else:
                conflict_lookup[field_name] = getattr(instance, field_name)

        return instance.__class__.objects.filter(**conflict_lookup).exclude(pk=instance.pk).first()