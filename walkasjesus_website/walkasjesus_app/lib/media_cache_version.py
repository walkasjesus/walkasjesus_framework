from django.core.cache import cache

MEDIA_CACHE_VERSION_KEY = 'media_fragment_cache_version:v1'
MEDIA_CACHE_VERSION_DEFAULT = 1


def get_media_cache_version():
    value = cache.get(MEDIA_CACHE_VERSION_KEY)
    if value is None:
        cache.set(MEDIA_CACHE_VERSION_KEY, MEDIA_CACHE_VERSION_DEFAULT, None)
        return MEDIA_CACHE_VERSION_DEFAULT

    try:
        return int(value)
    except (TypeError, ValueError):
        cache.set(MEDIA_CACHE_VERSION_KEY, MEDIA_CACHE_VERSION_DEFAULT, None)
        return MEDIA_CACHE_VERSION_DEFAULT


def bump_media_cache_version():
    current = get_media_cache_version()
    try:
        return cache.incr(MEDIA_CACHE_VERSION_KEY)
    except Exception:
        next_value = current + 1
        cache.set(MEDIA_CACHE_VERSION_KEY, next_value, None)
        return next_value
