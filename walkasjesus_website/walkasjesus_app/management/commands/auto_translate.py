import os

from django.apps import apps
from django.core.management import BaseCommand
from translate_tool import PoTranslator

from walkasjesus_website.settings import BASE_DIR, LANGUAGES, LOCALE_PATHS


class Command(BaseCommand):
    def handle(self, *args, **options):
        languages = [code for code, name in LANGUAGES]

        translator = PoTranslator()

        for language in languages:
            if language != 'en':
                for file_path in self._po_file_paths(language):
                    self.stdout.write(f'Auto-translating {file_path}')
                    translator.translate(file_path, 'en', language)

    def _po_file_paths(self, language):
        seen = set()
        base_dir = os.path.abspath(BASE_DIR)
        roots = list(LOCALE_PATHS)
        roots.extend(os.path.join(app_config.path, 'locale') for app_config in apps.get_app_configs())

        for root in roots:
            file_path = os.path.join(root, language, 'LC_MESSAGES', 'django.po')
            normalized = os.path.abspath(file_path)
            if not normalized.startswith(base_dir + os.sep):
                continue
            if normalized in seen or not os.path.exists(normalized):
                continue
            seen.add(normalized)
            yield normalized
