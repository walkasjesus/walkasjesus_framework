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
            entries_by_msgid = {entry.msgid: entry for entry in po if not entry.obsolete}
            obsolete_by_msgid = {entry.msgid: entry for entry in po.obsolete_entries()}
            revived = 0
            added = 0

            def ensure_msgid(value, source):
                nonlocal revived, added
                msgid = str(value or '').strip()
                if not msgid:
                    return

                entry = entries_by_msgid.get(msgid)
                if entry is None:
                    entry = obsolete_by_msgid.get(msgid)
                    if entry is not None:
                        entry.obsolete = False
                        revived += 1
                    else:
                        entry = polib.POEntry(msgid=msgid, msgstr='')
                        po.append(entry)
                        added += 1
                    entries_by_msgid[msgid] = entry
                occurrence = (source, '')
                if occurrence not in entry.occurrences:
                    entry.occurrences.append(occurrence)

            for model_name, fields in TRANSLATABLE_MODEL_FIELDS.items():
                model = apps.get_model('commandments_app', model_name)
                fields_to_sync = list(fields)
                if model_name == 'LawOfMessiah':
                    fields_to_sync.append('category')

                for field in fields_to_sync:
                    values = model.objects.exclude(**{field: ''}).values_list(field, flat=True).distinct()
                    for value in values.iterator():
                        ensure_msgid(value, f'model:{model_name}.{field}')

                for field in model._meta.fields:
                    for _, label in field.choices or []:
                        ensure_msgid(label, 'walkasjesus_app/translation.py')

            po.save()
            self.stdout.write(self.style.SUCCESS(f'{locale}: revived {revived}, added {added} model translation entries.'))