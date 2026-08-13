import os
from pathlib import Path

from bible_lib.simple_cache import SimpleCache


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if parent.name == 'walkasjesus_website':
            return parent.parent
    for parent in current.parents:
        if (parent / 'walkasjesus_website').exists():
            return parent
    return current.parent


def _project_cache_path() -> Path:
    project_root = _project_root()
    cache_dir = project_root / 'walkasjesus_website'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / 'bible_api_cache.json'


def _cache_ttl_seconds() -> int:
    try:
        from django.conf import settings

        value = getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', None)
        if value is not None:
            return int(value)
    except Exception:
        pass

    return int(os.getenv('BIBLE_API_CACHE_TTL_SECONDS', os.getenv('BIBLE_API_CACHE_TIMEOUT_SECONDS', 60 * 60 * 24 * 30)))


class Services:
    cache = SimpleCache(_project_cache_path(), ttl_seconds=_cache_ttl_seconds())
