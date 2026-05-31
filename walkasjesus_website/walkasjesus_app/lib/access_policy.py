from django.conf import settings


_LOCAL_DAVID_STERN_SOURCES = {
    'david-stern',
    'david_stern',
    'jnt-stern',
    'jnt_stern',
    'stern',
}


def _is_authenticated(request):
    user = getattr(request, 'user', None)
    return bool(getattr(user, 'is_authenticated', False))


def cjb_bible_id():
    return str(getattr(settings, 'CJB_BIBLE_ID', 'jnt-stern-en')).strip()


def is_cjb_bible_id(bible_id):
    return str(bible_id or '').strip().lower() == cjb_bible_id().lower()


def is_david_stern_source(source):
    return str(source or '').strip().lower() in _LOCAL_DAVID_STERN_SOURCES


def is_david_stern_commentary_allowed(request):
    login_only = bool(getattr(settings, 'DAVID_STERN_COMMENTARY_LOGGED_IN_ONLY', False))
    if not login_only:
        return True
    return _is_authenticated(request)


def is_bible_id_visible_for_request(request, bible_id):
    normalized_id = str(bible_id or '').strip()
    if not normalized_id:
        return False

    disabled = {str(item).strip() for item in getattr(settings, 'DISABLED_BIBLE_TRANSLATIONS', [])}
    if normalized_id in disabled:
        return False

    if is_cjb_bible_id(normalized_id):
        if not bool(getattr(settings, 'CJB_BIBLE_ENABLED', True)):
            return False
        if bool(getattr(settings, 'CJB_BIBLE_LOGGED_IN_ONLY', False)) and not _is_authenticated(request):
            return False

    return True


def filter_visible_bibles_for_request(request, bibles):
    return [b for b in bibles if is_bible_id_visible_for_request(request, getattr(b, 'id', ''))]
