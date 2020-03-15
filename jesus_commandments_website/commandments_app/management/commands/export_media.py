from django.core.management import BaseCommand

from commandments_app.models import *


class Command(BaseCommand):
    def __init__(self):
        pass
    def handle(self, *args, **options):
        commandments = Commandment.objects.all()

        for item in commandments:
            self.export_media(item)

    def export_media(self, obj: Commandment):
        pass
