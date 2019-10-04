from bible_lib import Bibles, Bible
from django.conf import settings
from django.utils import translation


class BibleTranslation:
    bibles = Bibles()

    def all(self) -> [Bible]:
        return self.bibles.list()

    def all_in_user_language(self) -> [Bible]:
        current_user_language = translation.get_language()
        return [b for b in self.all() if b.language == current_user_language]

    def all_in_supported_languages(self):
        languages = [code for code, name in settings.LANGUAGES]
        return [b for b in self.all() if b.language in languages]
