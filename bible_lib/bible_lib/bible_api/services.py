from pathlib import Path

from bible_lib.simple_cache import SimpleCache


def _project_cache_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    cache_dir = project_root / 'walkasjesus_website'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / 'bible_api_cache.json'


class Services:
    cache = SimpleCache(_project_cache_path())
