from abc import ABC
from typing import Any, Generic, TypeVar

from drift.client import GitClient
from drift.clients.mixins.retry import RetryMixin
from drift.logger import get_logger


T = TypeVar("T")


class BaseGitClient(GitClient, RetryMixin, Generic[T], ABC):  # noqa: UP046
    def __init__(
        self,
        client: T,
        repo_identifier: str,
        logger: Any | None = None,
        cache_ttl: int = 300,
        max_retries: int = 3,
        backoff_factor: float = 1.0,
    ) -> None:
        super().__init__()
        self.client = client
        self.repo_identifier = repo_identifier
        self.logger = logger or get_logger(self.__class__.__name__)
        self.cache_ttl = cache_ttl
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._repo: Any = None

    @property
    def repo(self) -> Any:
        if self._repo is None:
            self._repo = self._load_repository()
        return self._repo

    def _load_repository(self) -> Any:
        raise NotImplementedError
