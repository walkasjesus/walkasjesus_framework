import logging
import os

import polib
from django.core.management import BaseCommand
from import_tool import CommandmentImporter

from commandments_app.models import *
from volto_website.settings import BASE_DIR


class Command(BaseCommand):
    def handle(self, *args, **options):
        to_import_file_path = os.path.join(BASE_DIR, 'data', 'commandments.csv')
        importer = CommandmentImporter()
        commandments = importer.load(to_import_file_path)

        translation_file_path = os.path.join(BASE_DIR, 'locale', 'nl', 'LC_MESSAGES', 'django.po')
        po = polib.pofile(translation_file_path)

        for commandment in commandments:
            self._translate_commandment(po, commandment)

        po.save()

    def _translate_commandment(self, po, commandment):
        for entry in po.untranslated_entries() + po.translated_entries():
            if entry.msgid == commandment.title:
                entry.msgstr = commandment.title_nl
            if entry.msgid == commandment.description:
                entry.msgstr = commandment.description_nl