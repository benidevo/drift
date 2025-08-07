from abc import ABC
from collections.abc import Callable
from functools import wraps
from time import sleep
from typing import Any, Generic, TypeVar

from drift.client import GitClient
from drift.logger import get_logger


T = TypeVar("T")


class BaseGitClient(GitClient, Generic[T], ABC):
    def __init__(
        self,
        client: T,
        repo_identifier: str,
        logger: Any | None = None,
        cache_ttl: int = 300,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        self.client = client
        self.repo_identifier = repo_identifier
        self.logger = logger or get_logger(self.__class__.__name__)
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._repo: Any = None
        self._cache: dict[str, Any] = {}

    @property
    def repo(self) -> Any:
        if self._repo is None:
            self._repo = self._load_repository()
        return self._repo

    def _load_repository(self) -> Any:
        raise NotImplementedError

    def _with_retry(
        self, func: Callable[..., Any], max_retries: int | None = None
    ) -> Callable[..., Any]:
        if max_retries is None:
            max_retries = self.max_retries

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = self.backoff_factor * (2**attempt)
                        self.logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s..."
                        )
                        sleep(wait_time)
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry failed with no exception")

        return wrapper

    def _get_from_cache(self, key: str) -> Any | None:
        if key in self._cache:
            return self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        self._cache[key] = value

    def _clear_cache(self, pattern: str | None = None) -> None:
        if pattern is None:
            self._cache.clear()
        else:
            keys_to_delete = [k for k in self._cache if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
