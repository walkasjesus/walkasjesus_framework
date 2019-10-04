from django.utils import translation

from commandments_app.models import BibleTranslation


class UserPreferences:
    def __init__(self, session):
        self.session = session

    @property
    def bible(self):
        if 'bible_id' in self.session:
            return BibleTranslation().get(self.session['bible_id'])

        if self.language == 'nl':
            return BibleTranslation().get('hsv')

        return BibleTranslation().get('de4e12af7f28f599-01')

    @bible.setter
    def bible(self, value):
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
