import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path

from filelock import FileLock

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
        self._pending_updates = {}
        self._pending_deletions = set()
        self._disk_signature = None
        self._mutex = threading.RLock()
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_items_not_persisted = 0
        self.cache_path = cache_path
        self._file_lock = FileLock(str(cache_path) + '.lock')
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
        with self._mutex:
            self._sync_if_changed()
            existing = self._cache.get(key)
            if existing is not None and self._entry_is_valid(existing, now):
                self.cache_hits += 1
                return self._entry_value(existing)
            self.cache_misses += 1
        value = get_function(arguments)
        self.set_value(key, value)
        return value

    def __contains__(self, item):
        with self._mutex:
            self._sync_if_changed()
            entry = self._cache.get(str(item))
            return entry is not None and self._entry_is_valid(entry, time.time())

    def expires_at(self, key):
        """Return the expiry timestamp for a cached key, or None when absent/expired."""
        with self._mutex:
            self._sync_if_changed()
            entry = self._cache.get(str(key))
            if entry is None or not self._entry_is_valid(entry, time.time()):
                return None
            if isinstance(entry, dict):
                return entry.get('expires_at')
            return None

    def get_value(self, key, default=None):
        with self._mutex:
            self._sync_if_changed()
            value = self._cache.get(str(key))
            if value is None or not self._entry_is_valid(value, time.time()):
                return default
            return self._entry_value(value)

    def set_value(self, key, value, ttl_seconds=None):
        normalized_key = str(key)
        if ttl_seconds is None:
            ttl_seconds = self.ttl_seconds
        with self._mutex:
            entry = {'value': value, 'expires_at': time.time() + ttl_seconds}
            self._cache[normalized_key] = entry
            self._pending_updates[normalized_key] = entry
            self._pending_deletions.discard(normalized_key)
            self.cache_items_not_persisted = len(self._pending_updates) + len(self._pending_deletions)
            self.store_state()

    def clear_key(self, key: str):
        with self._mutex:
            key = str(key)
            self._cache.pop(key, None)
            self._pending_updates.pop(key, None)
            self._pending_deletions.add(key)
            self.cache_items_not_persisted = len(self._pending_updates) + len(self._pending_deletions)
            self.store_state()

    def cached_keys(self) -> [str]:
        with self._mutex:
            self._sync_if_changed()
            self._prune_expired()
            return list(self._cache.keys())

    def _signature(self):
        try:
            stat = self.cache_path.stat()
            return stat.st_ino, stat.st_mtime_ns, stat.st_size
        except FileNotFoundError:
            return None

    def _read_disk(self):
        try:
            with self.cache_path.open(encoding='utf-8') as file:
                loaded = json.load(file)
        except FileNotFoundError:
            return {}
        if not isinstance(loaded, dict):
            raise ValueError('Cache state must be a JSON object')
        return {
            key: value if isinstance(value, dict) and 'value' in value
            else {'value': value, 'expires_at': None}
            for key, value in loaded.items()
        }

    def _sync_if_changed(self):
        try:
            if self._signature() != self._disk_signature:
                self.load_state()
        except OSError as exc:
            self.logger.warning('Could not inspect cache state at %s: %s', self.cache_path, exc)

    def load_state(self):
        """" Load the cache content from disk. """
        with self._mutex:
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with self._file_lock:
                    loaded = self._read_disk()
                    signature = self._signature()
                loaded.update(self._pending_updates)
                for key in self._pending_deletions:
                    loaded.pop(key, None)
                self._cache = loaded
                self._disk_signature = signature
                self._prune_expired()
            except (OSError, ValueError, TypeError) as exc:
                self.logger.warning('Could not load cache state from %s: %s', self.cache_path, exc)

    def store_state(self):
        """" Store the cache content to disk. """
        with self._mutex:
            if not self._pending_updates and not self._pending_deletions:
                self._sync_if_changed()
                return
            temp_path = None
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                with self._file_lock:
                    merged = self._read_disk()
                    merged.update(self._pending_updates)
                    for key in self._pending_deletions:
                        merged.pop(key, None)
                    now = time.time()
                    merged = {key: value for key, value in merged.items() if self._entry_is_valid(value, now)}
                    with tempfile.NamedTemporaryFile(
                            mode='w', encoding='utf-8', dir=self.cache_path.parent,
                            prefix=self.cache_path.name + '.', suffix='.tmp', delete=False) as file:
                        temp_path = Path(file.name)
                        json.dump(merged, file, indent=4)
                    if self.cache_path.exists():
                        os.chmod(temp_path, self.cache_path.stat().st_mode & 0o777)
                    os.replace(temp_path, self.cache_path)
                    temp_path = None
                    self._disk_signature = self._signature()
                    self._cache = merged
                    self._pending_updates.clear()
                    self._pending_deletions.clear()
                    self.cache_items_not_persisted = 0
            except (OSError, ValueError, TypeError) as exc:
                self.logger.warning('Could not persist cache state to %s: %s', self.cache_path, exc)
            finally:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
