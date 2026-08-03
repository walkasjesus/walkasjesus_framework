import json
import hashlib
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Max

from walkasjesus_app.models import SwordCommentaryEntry, SwordCommentarySource


NT_BOOK_KEYS = {
    'matthew', 'mark', 'luke', 'john', 'acts', 'romans',
    '1corinthians', '2corinthians', 'galatians', 'ephesians', 'philippians', 'colossians',
    '1thessalonians', '2thessalonians', '1timothy', '2timothy', 'titus', 'philemon',
    'hebrews', 'james', '1peter', '2peter', '1john', '2john', '3john', 'jude', 'revelation',
}


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

    source_book_keys = defaultdict(set)
    source_ids = [str(source.source_id or '').strip() for source in sources if str(source.source_id or '').strip()]
    if source_ids:
        for source_id, book_key in (
            SwordCommentaryEntry.objects
            .filter(source__source_id__in=source_ids)
            .values_list('source__source_id', 'book_key')
            .distinct()
        ):
            normalized_book_key = normalize_book_key(book_key)
            if normalized_book_key:
                source_book_keys[str(source_id).strip()].add(normalized_book_key)

    commentators = []
    for source in sources:
        source_id = str(source.source_id or '').strip()
        if not source_id or source_id.lower() in disabled_ids:
            continue

        source_config = get_sword_source_config(source_id)
        native_language = str(source_config.get('native_language', getattr(source, 'language', '') or '')).strip().lower()[:2]
        auto_translate_raw = source_config.get('auto_translate', None)
        is_native_match = native_language == normalized_language
        if auto_translate_raw is None:
            auto_translate = is_native_match
        else:
            auto_translate = bool(auto_translate_raw)
            if is_native_match:
                auto_translate = True

        is_auto_translate_match = auto_translate and native_language == 'en' and normalized_language != 'en'
        if not is_native_match and not is_auto_translate_match:
            continue

        available_book_keys = sorted(source_book_keys.get(source_id, set()))
        supports_old_testament = True
        supports_new_testament = True
        if available_book_keys:
            supports_old_testament = any(book_key not in NT_BOOK_KEYS for book_key in available_book_keys)
            supports_new_testament = any(book_key in NT_BOOK_KEYS for book_key in available_book_keys)

        if 'supports_old_testament' in source_config:
            supports_old_testament = bool(source_config.get('supports_old_testament'))
        if 'supports_new_testament' in source_config:
            supports_new_testament = bool(source_config.get('supports_new_testament'))

        commentators.append({
            'id': source_id,
            'label': str(source.display_name or source.module_name or source_id).strip(),
            'copyright_text': str(source.copyright_text or '').strip(),
            'source_type': 'sword',
            'api_sources': [source_id],
            'auto_translate': auto_translate,
            'native_language': native_language,
            'supports_old_testament': supports_old_testament,
            'supports_new_testament': supports_new_testament,
            'available_book_keys': available_book_keys,
        })

    return commentators


def available_sword_commentators_json(language_code):
    signature = _sword_commentary_cache_signature(language_code)
    cache_key = f'sword-commentators-json:v1:{hashlib.sha256(signature.encode("utf-8")).hexdigest()}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    payload = json.dumps(available_sword_commentators(language_code), ensure_ascii=True)
    cache.set(cache_key, payload, timeout=60 * 60)
    return payload


def _sword_commentary_cache_signature(language_code):
    normalized_language = str(language_code or '').strip().lower()[:2]
    source_stats = SwordCommentarySource.objects.aggregate(count=Count('id'), max_id=Max('id'))
    entry_stats = SwordCommentaryEntry.objects.aggregate(count=Count('id'), max_id=Max('id'))
    disabled_ids = sorted(sword_disabled_source_ids())
    import_sources = getattr(settings, 'SWORD_COMMENTARY_IMPORT_SOURCES', []) or []
    source_config_ids = sorted(
        str(source.get('id', '') or '').strip().lower()
        for source in import_sources
        if isinstance(source, dict) and str(source.get('id', '') or '').strip()
    )
    signature = {
        'language': normalized_language,
        'enabled': sword_commentary_enabled(),
        'disabled': disabled_ids,
        'source_config_ids': source_config_ids,
        'source_count': source_stats.get('count') or 0,
        'source_max_id': source_stats.get('max_id') or 0,
        'entry_count': entry_stats.get('count') or 0,
        'entry_max_id': entry_stats.get('max_id') or 0,
    }
    return json.dumps(signature, sort_keys=True, separators=(',', ':'))