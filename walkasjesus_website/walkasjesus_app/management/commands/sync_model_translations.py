import os

import polib
from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand

from walkasjesus_app.translation import TRANSLATABLE_MODEL_FIELDS


class Command(BaseCommand):
    help = 'Keep database-backed translatable model text active in Django PO files.'

    def add_arguments(self, parser):
        parser.add_argument('--locale', action='append', dest='locales')

    def handle(self, *args, **options):
        locales = options.get('locales') or [code for code, _ in settings.LANGUAGES if code != settings.LANGUAGE_CODE]

        for locale in locales:
            po_path = os.path.join(settings.BASE_DIR, 'translations', 'locale', locale, 'LC_MESSAGES', 'django.po')
            if not os.path.exists(po_path):
                self.stdout.write(self.style.WARNING(f'Skipping missing PO file: {po_path}'))
                continue

            po = polib.pofile(po_path)
            active_msgids = {entry.msgid for entry in po if not entry.obsolete}
            revived = 0
            added = 0

            def ensure_msgid(value):
                nonlocal revived, added
                msgid = str(value or '').strip()
                if not msgid or msgid in active_msgids:
                    return

                obsolete_entry = next((entry for entry in po.obsolete_entries() if entry.msgid == msgid), None)
                if obsolete_entry:
                    obsolete_entry.obsolete = False
                    active_msgids.add(msgid)
                    revived += 1
                else:
                    po.append(polib.POEntry(msgid=msgid, msgstr=''))
                    active_msgids.add(msgid)
                    added += 1

            for model_name, fields in TRANSLATABLE_MODEL_FIELDS.items():
                model = apps.get_model('commandments_app', model_name)
                fields_to_sync = list(fields)
                if model_name == 'LawOfMessiah':
                    fields_to_sync.append('category')

                for field in fields_to_sync:
                    values = model.objects.exclude(**{field: ''}).values_list(field, flat=True).distinct()
                    for value in values.iterator():
                        ensure_msgid(value)

                for field in model._meta.fields:
                    for _, label in field.choices or []:
                        ensure_msgid(label)

            po.save()
            self.stdout.write(self.style.SUCCESS(f'{locale}: revived {revived}, added {added} model translation entries.'))