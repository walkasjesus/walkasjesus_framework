from django.utils import translation
from walkasjesus_app.models import BibleTranslation
from walkasjesus_website import settings

class UserPreferences:
    PER_LANGUAGE_BIBLE_SESSION_KEY = 'bible_id_per_language'

    def __init__(self, session):
        self.session = session

    def _current_language_code(self):
        return str(self.language or '').strip().lower()[:2]

    def _stored_bibles_by_language(self):
        raw_value = self.session.get(self.PER_LANGUAGE_BIBLE_SESSION_KEY, {})
        if not isinstance(raw_value, dict):
            return {}
        return {
            str(lang).strip().lower()[:2]: str(bible_id).strip()
            for lang, bible_id in raw_value.items()
            if str(lang).strip() and str(bible_id).strip()
        }

    @property
    def bible(self):
        current_language = self._current_language_code()

        # Prefer an explicitly stored Bible preference for the active language.
        preferred_bibles = self._stored_bibles_by_language()
        preferred_bible_id = preferred_bibles.get(current_language, '')
        if preferred_bible_id and preferred_bible_id not in settings.DISABLED_BIBLE_TRANSLATIONS:
            return BibleTranslation().get(preferred_bible_id)

        # Backward compatible fallback for old sessions.
        if 'bible_id' in self.session:
            bible_id = str(self.session['bible_id'])
            if bible_id not in settings.DISABLED_BIBLE_TRANSLATIONS:
                legacy_bible = BibleTranslation().get(bible_id)
                if str(getattr(legacy_bible, 'language', '')).strip().lower()[:2] == current_language:
                    return legacy_bible

        # Fallback to default Bible translation
        default_bible = settings.DEFAULT_BIBLE_PER_LANGUAGE.get(current_language, settings.DEFAULT_BIBLE_ANY_LANGUAGE)
        
        # Ensure the default Bible is not disabled
        if default_bible not in settings.DISABLED_BIBLE_TRANSLATIONS:
            return BibleTranslation().get(default_bible)

        # Handle the case where the default Bible is disabled
        fallback_bible = settings.DEFAULT_BIBLE_ANY_LANGUAGE
        return BibleTranslation().get(fallback_bible)

    @bible.setter
    def bible(self, value):
        if value.id not in settings.DISABLED_BIBLE_TRANSLATIONS:
            self.session['bible_id'] = value.id
            preferred_bibles = self._stored_bibles_by_language()
            preferred_bibles[self._current_language_code()] = value.id
            self.session[self.PER_LANGUAGE_BIBLE_SESSION_KEY] = preferred_bibles

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

