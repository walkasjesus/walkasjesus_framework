from django.conf import settings
from django.utils import translation

from walkasjesus_app.lib.access_policy import is_david_stern_commentary_allowed, cjb_bible_id, is_bible_id_visible_for_request
from walkasjesus_app.lib.sword_commentary import available_sword_commentators_json, sword_commentary_enabled
from walkasjesus_app.models import BibleTranslation, UserPreferences


def bible_translation(request):
    return {
        'bible_translation': BibleTranslation(),
        'cjb_bible_id': cjb_bible_id(),
        'cjb_bible_visible': is_bible_id_visible_for_request(request, cjb_bible_id()),
    }


def user_preferences(request):
    return {
        'user_preferences': UserPreferences(request.session),
    }


def cache_settings(request):
    disabled_commentators = getattr(settings, 'COMMENTARY_DISABLED_SOURCES',
                                    getattr(settings, 'SCRIPTURA_DISABLED_COMMENTATORS', []))
    if not isinstance(disabled_commentators, (list, tuple, set)):
        disabled_commentators = []
    disabled_commentators = [str(item).strip().lower() for item in disabled_commentators if str(item).strip()]

    disabled_sword_sources = getattr(settings, 'SWORD_DISABLED_COMMENTARY_SOURCES', [])
    if not isinstance(disabled_sword_sources, (list, tuple, set)):
        disabled_sword_sources = []
    disabled_commentators.extend([str(item).strip().lower() for item in disabled_sword_sources if str(item).strip()])

    david_stern_available = is_david_stern_commentary_allowed(request)
    if not bool(getattr(settings, 'CJB_BIBLE_ENABLED', True)):
        user = getattr(request, 'user', None)
        if not bool(getattr(user, 'is_authenticated', False)):
            david_stern_available = False
    if not david_stern_available:
        disabled_commentators.append('david-stern')

    disabled_commentators = sorted(set(disabled_commentators))

    language_code = str(translation.get_language() or 'en').strip().lower()[:2]

    return {
        'cache_timeout': 3600,
        'cache_on_language': UserPreferences(request.session).language,
        'cache_on_multi_language': UserPreferences(request.session).languages,
        'cache_on_bible': translation.get_language() + '_' + UserPreferences(request.session).bible.id,
        'cache_on_kids_mode': 'kids' if request.COOKIES.get('jc_kids_mode') else 'default',
        'commentary_cache_timeout_seconds': int(getattr(settings, 'COMMENTARY_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30 * 6)),
        'david_stern_commentary_footer_text': str(getattr(settings, 'DAVID_STERN_COMMENTARY_FOOTER_TEXT', '')).strip(),
        'david_stern_commentary_available': david_stern_available,
        'scriptura_disabled_commentators': ','.join(disabled_commentators),
        'sword_commentary_enabled': sword_commentary_enabled(),
        'sword_commentators_json': available_sword_commentators_json(language_code),
    }
