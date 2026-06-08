import json

from django.conf import settings

from walkasjesus_app.models import SwordCommentarySource


def normalize_book_key(value):
    return ''.join(ch for ch in str(value or '').lower() if ch.isalnum())


def sword_commentary_enabled():
    return bool(getattr(settings, 'SWORD_COMMENTARY_ENABLED', True))


def sword_disabled_source_ids():
    # Sources can be disabled via the per-source `enabled: false` field, or the legacy list.
    disabled = set()
    import_sources = getattr(settings, 'SWORD_COMMENTARY_IMPORT_SOURCES', []) or []
    for src in import_sources:
        if isinstance(src, dict) and not src.get('enabled', True):
            source_id = str(src.get('id', '') or '').strip().lower()
            if source_id:
                disabled.add(source_id)
    # Legacy generic disabled list (covers all source types).
    legacy = getattr(settings, 'COMMENTARY_DISABLED_SOURCES',
                     getattr(settings, 'SWORD_DISABLED_COMMENTARY_SOURCES', []))
    if isinstance(legacy, (list, tuple, set)):
        disabled.update(str(item).strip().lower() for item in legacy if str(item).strip())
    return disabled


def get_sword_source_config(source_id):
    """Return the settings dict for a given SWORD source id, or an empty dict."""
    normalized = str(source_id or '').strip().lower()
    for src in (getattr(settings, 'SWORD_COMMENTARY_IMPORT_SOURCES', []) or []):
        if isinstance(src, dict) and str(src.get('id', '') or '').strip().lower() == normalized:
            return src
    return {}


def available_sword_commentators(language_code):
    normalized_language = str(language_code or '').strip().lower()[:2]
    if not sword_commentary_enabled() or not normalized_language:
        return []

    disabled_ids = sword_disabled_source_ids()
    sources = SwordCommentarySource.objects.filter(is_enabled=True).order_by('sort_order', 'display_name', 'source_id')

    commentators = []
    for source in sources:
        source_id = str(source.source_id or '').strip()
        if not source_id or source_id.lower() in disabled_ids:
            continue

        source_config = get_sword_source_config(source_id)
        native_language = str(source_config.get('native_language', getattr(source, 'language', '') or '')).strip().lower()[:2]
        auto_translate = bool(source_config.get('auto_translate', False))

        is_native_match = native_language == normalized_language
        is_auto_translate_match = auto_translate and native_language == 'en' and normalized_language != 'en'
        if not is_native_match and not is_auto_translate_match:
            continue

        commentators.append({
            'id': source_id,
            'label': str(source.display_name or source.module_name or source_id).strip(),
            'copyright_text': str(source.copyright_text or '').strip(),
            'source_type': 'sword',
            'api_sources': [source_id],
            'auto_translate': auto_translate,
            'native_language': native_language,
        })

    return commentators


def available_sword_commentators_json(language_code):
    return json.dumps(available_sword_commentators(language_code), ensure_ascii=True)