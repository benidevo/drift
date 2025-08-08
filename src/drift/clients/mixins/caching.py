from collections.abc import Callable
from functools import wraps
import hashlib
import json
from typing import Any

from cachetools import TTLCache

from drift.logger import get_logger


class CacheMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        cache_ttl = getattr(self, "cache_ttl", 300)
        max_size = getattr(self, "cache_max_size", 500)
        self._cache: TTLCache[str, Any] = TTLCache(maxsize=max_size, ttl=cache_ttl)
        self._cache_logger = get_logger(f"{self.__class__.__name__}.CacheMixin")
        self._cache_ttl = cache_ttl

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
                    self._cache_logger.debug(f"Cache hit for {cache_key}")
                    return self._cache[cache_key]

                self._cache_logger.debug(f"Cache miss for {cache_key}")
                result = func(*args, **kwargs)
                self._cache[cache_key] = result

                return result

            return wrapper

        return decorator

    def clear_cache(self, pattern: str | None = None) -> None:
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

    def get_cache_stats(self) -> dict[str, Any]:
        return {
            "total_entries": len(self._cache),
            "max_size": self._cache.maxsize,
            "ttl": self._cache.ttl,
            "cache_keys": list(self._cache.keys()),
        }
