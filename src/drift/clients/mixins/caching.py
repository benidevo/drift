from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
import hashlib
import json
import time
from typing import Any

from drift.logger import get_logger


@dataclass(frozen=True, slots=True)
class CacheEntry:
    value: Any
    expires_at: float

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache: dict[str, CacheEntry] = {}
        self._cache_logger = get_logger(f"{self.__class__.__name__}.CacheMixin")
        self._cache_ttl = getattr(self, "cache_ttl", 300)

    def _make_cache_key(self, *args: Any, **kwargs: Any) -> str:
        key_data = {
            "args": [str(arg) for arg in args],
            "kwargs": {k: str(v) for k, v in sorted(kwargs.items())},
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def with_cache(
        self, ttl: int | None = None, key_prefix: str = ""
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Decorator to cache function results with TTL.

        Args:
            ttl: Time-to-live in seconds (uses instance default if None)
            key_prefix: Prefix for cache keys
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                cache_ttl = ttl if ttl is not None else self._cache_ttl

                if cache_ttl <= 0:
                    return func(*args, **kwargs)

                func_args = args[1:] if args and args[0] == self else args
                cache_key = (
                    f"{key_prefix}{func.__name__}:"
                    f"{self._make_cache_key(*func_args, **kwargs)}"
                )

                if cache_key in self._cache:
                    entry = self._cache[cache_key]
                    if not entry.is_expired():
                        self._cache_logger.debug(f"Cache hit for {cache_key}")
                        return entry.value
                    else:
                        self._cache_logger.debug(f"Cache expired for {cache_key}")
                        del self._cache[cache_key]

                self._cache_logger.debug(f"Cache miss for {cache_key}")
                result = func(*args, **kwargs)

                self._cache[cache_key] = CacheEntry(
                    value=result, expires_at=time.time() + cache_ttl
                )

                return result

            return wrapper

        return decorator

    def clear_cache(self, pattern: str | None = None) -> None:
        """
        Clear cache entries.

        Args:
            pattern: Clear only keys containing this pattern (clears all if None)
        """
        if pattern is None:
            self._cache_logger.info("Clearing entire cache")
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            self._cache_logger.info(
                f"Clearing {len(keys_to_delete)} cache entries matching '{pattern}'"
            )
            for key in keys_to_delete:
                del self._cache[key]

    def evict_expired(self) -> None:
        expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
        self._cache_logger.info(f"Evicting {len(expired_keys)} expired cache entries")
        for key in expired_keys:
            del self._cache[key]

    def get_cache_stats(self) -> dict[str, Any]:
        total_entries = len(self._cache)
        expired_entries = sum(1 for entry in self._cache.values() if entry.is_expired())
        return {
            "total_entries": total_entries,
            "expired_entries": expired_entries,
            "active_entries": total_entries - expired_entries,
            "cache_keys": list(self._cache.keys()),
        }
