from pathlib import Path

from bible_lib.simple_cache import SimpleCache


class Services:
    cache = SimpleCache(Path('bible_api_cache.json'))
