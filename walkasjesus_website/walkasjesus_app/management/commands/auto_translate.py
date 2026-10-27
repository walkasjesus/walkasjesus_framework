import os

from django.apps import apps
from django.core.management import BaseCommand, CommandError
from translate_tool import PoTranslator

from walkasjesus_website.settings import BASE_DIR, LANGUAGES, LOCALE_PATHS


class Command(BaseCommand):
    help = 'Translate missing or fuzzy PO entries, preserving existing translations.'

    def add_arguments(self, parser):
        parser.add_argument('--locale', action='append', dest='locales')

    def handle(self, *args, **options):
        supported_languages = [code for code, name in LANGUAGES]
        languages = options.get('locales') or supported_languages
        unsupported = set(languages) - set(supported_languages)
        if unsupported:
            raise CommandError(f'Unsupported locales: {", ".join(sorted(unsupported))}')

        translator = PoTranslator()

        for language in languages:
            if language != 'en':
                paths = list(self._po_file_paths(language))
                if not paths:
                    raise CommandError(f'No PO files found for {language}; run makemessages first.')
                for file_path in paths:
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
