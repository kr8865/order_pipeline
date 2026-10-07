"""Tiny thread-safe TTL cache (good enough for a single process; swap for Redis in production)."""
from __future__ import annotations

import threading
import time
from functools import wraps
from typing import Any, Callable


class TTLCache:
    def __init__(self) -> None:
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            hit = self._store.get(key)
            if not hit:
                return None
            expires, value = hit
            if expires < time.time():
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        with self._lock:
            self._store[key] = (time.time() + ttl, value)

    def clear(self, prefix: str = "") -> None:
        with self._lock:
            for k in [k for k in self._store if k.startswith(prefix)]:
                self._store.pop(k, None)


cache = TTLCache()


def cached(prefix: str, ttl: int, version_fn: Callable[[], Any] | None = None) -> Callable:
    """Cache a function's result keyed by its (hashable) keyword/positional args.

    If `version_fn` is given, its value is part of the key, so a change in the data (even one made
    by another process) makes old entries unreachable immediately."""
    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            version = version_fn() if version_fn else ""
            key = f"{prefix}:v{version}:{args!r}:{sorted(kwargs.items())!r}"
            hit = cache.get(key)
            if hit is not None:
                return hit
            value = fn(*args, **kwargs)
            cache.set(key, value, ttl)
            return value
        return wrapper
    return decorator
