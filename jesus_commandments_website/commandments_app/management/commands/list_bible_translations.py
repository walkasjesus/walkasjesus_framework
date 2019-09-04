from django.core.management import BaseCommand

from commandments_app.models import BibleTranslation


class Command(BaseCommand):
    def handle(self, *args, **options):
        bibles = BibleTranslation().all_in_supported_languages()

        for bible in bibles:
            print(f'id: {bible.id} name: {bible.name}')
