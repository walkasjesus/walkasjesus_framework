from django.utils import translation

from commandments_app.models import BibleTranslation, UserPreferences


def bible_translation(request):
    return {
        'bible_translation': BibleTranslation(),
    }


def user_preferences(request):
    return {
        'user_preferences': UserPreferences(request.session),
    }


def cache_settings(request):
    return {
        'cache_timeout': 3600,
        'cache_on_language': UserPreferences(request.session).language,
        'cache_on_multi_language': UserPreferences(request.session).languages,
        'cache_on_bible': translation.get_language() + '_' + UserPreferences(request.session).bible.id,
    }
