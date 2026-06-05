import json

from django.conf import settings

from walkasjesus_app.models import SwordCommentarySource


def normalize_book_key(value):
    return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())


def sword_commentary_enabled():
    return bool(getattr(settings, 'SWORD_COMMENTARY_ENABLED', True))


def sword_disabled_source_ids():
    disabled_sources = getattr(settings, 'SWORD_DISABLED_COMMENTARY_SOURCES', [])
    if not isinstance(disabled_sources, (list, tuple, set)):
        return set()
    return {str(item).strip().lower() for item in disabled_sources if str(item).strip()}


def available_sword_commentators(language_code):
    normalized_language = str(language_code or '').strip().lower()[:2]
    if not sword_commentary_enabled() or not normalized_language:
        return []

    disabled_ids = sword_disabled_source_ids()
    sources = SwordCommentarySource.objects.filter(language=normalized_language, is_enabled=True).order_by('sort_order', 'display_name', 'source_id')

    commentators = []
    for source in sources:
        source_id = str(source.source_id or '').strip()
        if not source_id or source_id.lower() in disabled_ids:
            continue

        commentators.append({
            'id': source_id,
            'label': str(source.display_name or source.module_name or source_id).strip(),
            'copyright_text': str(source.copyright_text or '').strip(),
            'source_type': 'sword',
            'api_sources': [source_id],
        })

    return commentators


def available_sword_commentators_json(language_code):
    return json.dumps(available_sword_commentators(language_code), ensure_ascii=True)