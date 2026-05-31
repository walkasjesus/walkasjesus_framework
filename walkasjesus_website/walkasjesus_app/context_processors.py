from django.conf import settings
from django.utils import translation

from walkasjesus_app.lib.access_policy import is_david_stern_commentary_allowed
from walkasjesus_app.models import BibleTranslation, UserPreferences


def bible_translation(request):
    return {
        'bible_translation': BibleTranslation(),
    }


def user_preferences(request):
    return {
        'user_preferences': UserPreferences(request.session),
    }


def cache_settings(request):
    disabled_commentators = getattr(settings, 'SCRIPTURA_DISABLED_COMMENTATORS', [])
    if not isinstance(disabled_commentators, (list, tuple, set)):
        disabled_commentators = []
    disabled_commentators = [str(item).strip().lower() for item in disabled_commentators if str(item).strip()]

    return {
        'cache_timeout': 3600,
        'cache_on_language': UserPreferences(request.session).language,
        'cache_on_multi_language': UserPreferences(request.session).languages,
        'cache_on_bible': translation.get_language() + '_' + UserPreferences(request.session).bible.id,
        'cache_on_kids_mode': 'kids' if request.COOKIES.get('jc_kids_mode') else 'default',
        'commentary_cache_timeout_seconds': int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6)),
        'david_stern_commentary_footer_text': str(getattr(settings, 'DAVID_STERN_COMMENTARY_FOOTER_TEXT', '')).strip(),
        'david_stern_commentary_available': is_david_stern_commentary_allowed(request),
        'scriptura_disabled_commentators': ','.join(disabled_commentators),
    }
