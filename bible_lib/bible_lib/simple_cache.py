import json
import logging
import os
import time
from pathlib import Path

DEFAULT_CACHE_TTL_SECONDS = 60 * 60 * 24 * 30


def _resolve_ttl_seconds(ttl_seconds=None):
    if ttl_seconds is not None:
        return int(ttl_seconds)

    try:
        from django.conf import settings

        value = getattr(settings, 'BIBLE_API_CACHE_TIMEOUT_SECONDS', None)
        if value is not None:
            return int(value)
    except Exception:
        pass

    env_value = os.getenv('BIBLE_API_CACHE_TTL_SECONDS', os.getenv('BIBLE_API_CACHE_TIMEOUT_SECONDS', DEFAULT_CACHE_TTL_SECONDS))
    return int(env_value)


class SimpleCache:
    def __init__(self, cache_path: Path = Path('cache.json'), ttl_seconds: int = None):
        self._cache = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_items_not_persisted = 0
        self.cache_path = cache_path
        self.ttl_seconds = _resolve_ttl_seconds(ttl_seconds)
        self.logger = logging.getLogger()
        self.load_state()

    @staticmethod
    def _entry_value(entry):
        if isinstance(entry, dict) and 'value' in entry:
            return entry['value']
        return entry

    @staticmethod
    def _entry_is_valid(entry, now):
        if not isinstance(entry, dict):
            return True
        expires_at = entry.get('expires_at')
        if expires_at is None:
            return True
        return float(expires_at) > now

    def _prune_expired(self):
        now = time.time()
        expired_keys = [
            key for key, value in self._cache.items()
            if not self._entry_is_valid(value, now)
        ]
        for key in expired_keys:
            self._cache.pop(key, None)

    def get(self, get_function, arguments):
        key = str(arguments)
        now = time.time()

        existing = self._cache.get(key)
        if existing is not None and self._entry_is_valid(existing, now):
            self.cache_hits += 1
            return self._entry_value(existing)

        self.cache_misses += 1
        self.cache_items_not_persisted += 1
        value = get_function(arguments)
        # Stringify when storing, otherwise we run into problems
        # when serializing to disk, where json serializer makes int 5 a string '5'
        # which will be seen as something different when reloading the data.
        self._cache[key] = {
            'value': value,
            'expires_at': now + self.ttl_seconds,
        }
        self.store_state()
        return value

    def __contains__(self, item):
        key = str(item)
        if key not in self._cache:
            return False
        if not self._entry_is_valid(self._cache[key], time.time()):
            self._cache.pop(key, None)
            return False
        return True

    def get_value(self, key, default=None):
        normalized_key = str(key)
        value = self._cache.get(normalized_key)
        if value is None:
            return default
        if not self._entry_is_valid(value, time.time()):
            self._cache.pop(normalized_key, None)
            return default
        return self._entry_value(value)

    def set_value(self, key, value, ttl_seconds=None):
        normalized_key = str(key)
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds
        self._cache[normalized_key] = {
            'value': value,
            'expires_at': time.time() + ttl_seconds,
        }
        self.store_state()

    def clear_key(self, key: str):
        self._cache.pop(str(key), None)
        self.store_state()

    def cached_keys(self) -> [str]:
        return list(self._cache.keys())

    def load_state(self):
        """" Load the cache content from disk. """
        if not self.cache_path.exists():
            self.logger.info(f'Could not find cache at {self.cache_path}')
            return

        with self.cache_path.open() as file:
            loaded = json.load(file)

        if not isinstance(loaded, dict):
            self._cache = {}
            return

        self._cache = {
            key: (
                value if isinstance(value, dict) and 'value' in value
                else {'value': value, 'expires_at': None}
            )
            for key, value in loaded.items()
        }
        self._prune_expired()

    def store_state(self):
        """" Store the cache content to disk. """
        self._prune_expired()
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self.cache_path.open('w+') as file:
            json.dump(self._cache, file, indent=4)
            self.cache_items_not_persisted = 0
