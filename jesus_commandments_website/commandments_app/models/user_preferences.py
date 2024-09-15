from django.utils import translation

from commandments_app.models import BibleTranslation
from jesus_commandments_website import settings


class UserPreferences:
    def __init__(self, session):
        self.session = session

    @property
    def bible(self):
        # Check if a translation ID is stored in the session
        if 'bible_id' in self.session:
            bible_id = self.session['bible_id']
            if bible_id not in settings.DISABLED_BIBLE_TRANSLATIONS:
                return BibleTranslation().get(bible_id)

<<<<<<< HEAD
        # Fallback to default Bible translation
        default_bible = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(self.language, settings.DEFAULT_BIBLE_ANY_LANGUAGE)
        # Ensure the default Bible is not disabled
        if default_bible not in settings.DISABLED_BIBLE_TRANSLATIONS:
            return BibleTranslation().get(default_bible)

        # Handle the case where the default Bible is disabled
        fallback_bible = settings.DEFAULT_BIBLE_ANY_LANGUAGE
        return BibleTranslation().get(fallback_bible)
=======
        default_bible = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(self.language, settings.DEFAULT_BIBLE_ANY_LANGUAGE)
        return BibleTranslation().get(default_bible)
>>>>>>> 869e54825843f434f1f30a0a8e82a1a1018e4800

    @bible.setter
    def bible(self, value):
        if value.id not in settings.DISABLED_BIBLE_TRANSLATIONS:
            self.session['bible_id'] = value.id


    @property
    def language(self):
        return translation.get_language()

    @property
    def languages(self):
        """ A user can select multiple languages (so more media is shown for example)"""
        if 'languages' in self.session and self.session['languages'] is not None:
            return self.session['languages']

        # If nothing is specified, default to user main language and english as many items are available in english.
        return [self.language, 'en']

    @languages.setter
    def languages(self, value) -> []:
        # Sort so when using in comparison or cache key [en, nl] is the same cache as [nl, en]
        self.session['languages'] = sorted(value)

