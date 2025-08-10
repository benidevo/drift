import logging
from typing import Any

from drift.client import GitClient
from drift.clients.factory import GitClientFactory
from drift.config import DriftConfig


class ConfigAdapter:
    def __init__(self, drift_config: DriftConfig):
        self._config = drift_config

    @property
    def provider(self) -> Any:
        return self._config.provider

    @property
    def token(self) -> str:
        return self._config.token

    @property
    def repo_identifier(self) -> str:
        return self._config.repo

    @property
    def base_url(self) -> str | None:
        return self._config.base_url

    @property
    def logger(self) -> Any | None:
        logger = logging.getLogger("drift")
        logger.setLevel(self._config.log_level)
        return logger

    @property
    def cache_ttl(self) -> int:
        return self._config.cache_ttl

    @property
    def cache_maxsize(self) -> int:
        return 500

    @property
    def max_retries(self) -> int:
        return self._config.max_retries

    @property
    def backoff_factor(self) -> float:
        return self._config.backoff_factor

    @property
    def per_page(self) -> int:
        return 100


class DriftApplication:
    def __init__(self, config: DriftConfig):
        self.config = config
        self._client: GitClient | None = None

    @property
    def client(self) -> GitClient:
        if self._client is None:
            adapter = ConfigAdapter(self.config)
            self._client = GitClientFactory.create(adapter)
        return self._client

    @classmethod
    def from_env(cls) -> "DriftApplication":
        config = DriftConfig.from_env()
        return cls(config)

    @classmethod
    def from_file(cls, path: str) -> "DriftApplication":
        config = DriftConfig.from_file(path)
        return cls(config)

    def analyze_pr(self, pr_id: str) -> dict:
        client = self.client

        pr_info = client.get_pr_info(pr_id)

        diff_data = client.get_diff_data(pr_id)

        commits = client.get_commit_messages(pr_id)

        comments = client.get_existing_comments(pr_id)

        return {
            "pr_info": pr_info,
            "diff_data": diff_data,
            "commits": commits,
            "comments": comments,
        }

    def post_review(self, pr_id: str, review_comment: str) -> None:
        self.client.post_comment(pr_id, review_comment)

    def update_review(self, pr_id: str, comment_id: str, review_comment: str) -> None:
        self.client.update_comment(pr_id, comment_id, review_comment)


def create_app_from_env() -> DriftApplication:
    return DriftApplication.from_env()


def create_app_from_file(config_path: str) -> DriftApplication:
    return DriftApplication.from_file(config_path)
