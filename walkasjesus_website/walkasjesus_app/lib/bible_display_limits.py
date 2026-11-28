"""Per-translation verse display limits driven by license agreements.

Translations listed in settings.BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID (e.g. NBV21 and
BGT under the NBG license: "maximaal 5 Bijbelverzen per keer") are clamped to that
number of verses per request. All other translations may display a whole chapter.
"""
from django.conf import settings


def chapter_verse_cap():
    """Hard upper bound for whole-chapter display (longest chapter is Psalm 119)."""
    return int(getattr(settings, 'BIBLE_STUDY_CHAPTER_VERSE_CAP', 200))


def max_verses_for_bible_id(bible_id):
    """License limit for one translation, or None when a whole chapter is allowed."""
    limits = getattr(settings, 'BIBLE_STUDY_MAX_VERSES_BY_BIBLE_ID', {}) or {}
    try:
        value = limits.get(str(bible_id or '').strip())
    except AttributeError:
        return None
    return int(value) if value else None


def effective_max_verses(bible_ids):
    """Strictest license limit across the selected translations.

    Returns the chapter cap when none of the translations is license-limited.
    """
    bounded = [
        limit for limit in (max_verses_for_bible_id(bid) for bid in (bible_ids or []))
        if limit
    ]
    return min(bounded) if bounded else chapter_verse_cap()


def license_limited_bible_ids(bible_ids):
    """Subset of the given bible ids that carry a license verse limit."""
    return [bid for bid in (bible_ids or []) if max_verses_for_bible_id(bid)]
