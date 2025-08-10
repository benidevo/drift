from dataclasses import dataclass
import os
from pathlib import Path
import re

import yaml

from drift.client import GitProvider
from drift.exceptions import ConfigurationError


@dataclass(frozen=True)
class DriftConfig:
    provider: GitProvider
    token: str
    repo: str
    base_url: str | None = None
    cache_ttl: int = 300
    max_retries: int = 3
    backoff_factor: float = 1.0
    timeout: int = 30
    log_level: str = "INFO"
    log_format: str = "json"
    connection_pool_size: int = 10

    @staticmethod
    def _safe_parse_int(value: str, name: str, default: int) -> int:
        if not value:
            return default
        try:
            return int(value)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                f"Invalid integer value for {name}: '{value}'. Must be a valid integer."
            ) from e

    @staticmethod
    def _safe_parse_float(value: str, name: str, default: float) -> float:
        if not value:
            return default
        try:
            return float(value)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                f"Invalid float value for {name}: '{value}'. Must be a valid number."
            ) from e

    def __post_init__(self) -> None:
        if self.cache_ttl < 0:
            raise ConfigurationError("cache_ttl must be non-negative")
        if self.max_retries < 0:
            raise ConfigurationError("max_retries must be non-negative")
        if self.backoff_factor < 0:
            raise ConfigurationError("backoff_factor must be non-negative")
        if self.timeout <= 0:
            raise ConfigurationError("timeout must be positive")
        if self.connection_pool_size <= 0:
            raise ConfigurationError("connection_pool_size must be positive")
        if not self.token:
            raise ConfigurationError("Token is required")
        if not self.repo:
            raise ConfigurationError("Repository is required")

    @classmethod
    def from_env(cls) -> "DriftConfig":
        provider_str = os.environ.get("DRIFT_PROVIDER", "").lower()
        if not provider_str:
            raise ConfigurationError("DRIFT_PROVIDER environment variable not set")

        try:
            provider = GitProvider(provider_str)
        except ValueError as e:
            raise ConfigurationError(f"Invalid provider: {provider_str}") from e

        token_env = f"{provider.value.upper()}_TOKEN"
        token = os.environ.get(token_env)
        if not token:
            raise ConfigurationError(f"{token_env} environment variable not set")

        repo = os.environ.get("DRIFT_REPO")
        if not repo:
            raise ConfigurationError("DRIFT_REPO environment variable not set")

        base_url = None
        if provider == GitProvider.GITHUB:
            base_url = os.environ.get("GITHUB_BASE_URL")
        elif provider == GitProvider.GITLAB:
            base_url = os.environ.get("GITLAB_URL")

        return cls(
            provider=provider,
            token=token,
            repo=repo,
            base_url=base_url,
            cache_ttl=cls._safe_parse_int(
                os.environ.get("DRIFT_CACHE_TTL", ""), "DRIFT_CACHE_TTL", 300
            ),
            max_retries=cls._safe_parse_int(
                os.environ.get("DRIFT_MAX_RETRIES", ""), "DRIFT_MAX_RETRIES", 3
            ),
            backoff_factor=cls._safe_parse_float(
                os.environ.get("DRIFT_BACKOFF_FACTOR", ""), "DRIFT_BACKOFF_FACTOR", 1.0
            ),
            timeout=cls._safe_parse_int(
                os.environ.get("DRIFT_TIMEOUT", ""), "DRIFT_TIMEOUT", 30
            ),
            log_level=os.environ.get("DRIFT_LOG_LEVEL", "INFO"),
            log_format=os.environ.get("DRIFT_LOG_FORMAT", "json"),
            connection_pool_size=cls._safe_parse_int(
                os.environ.get("DRIFT_CONNECTION_POOL_SIZE", ""),
                "DRIFT_CONNECTION_POOL_SIZE",
                10,
            ),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "DriftConfig":
        path = Path(path)
        if not path.exists():
            raise ConfigurationError(f"Configuration file not found: {path}")

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in configuration file: {e}") from e

        if not data:
            raise ConfigurationError("Configuration file is empty")

        provider_str = data.get("provider", "").lower()
        if not provider_str:
            raise ConfigurationError("provider not specified in configuration")

        try:
            provider = GitProvider(provider_str)
        except ValueError as e:
            raise ConfigurationError(f"Invalid provider: {provider_str}") from e

        auth = data.get("authentication", {})
        token = auth.get("token")
        if not token:
            raise ConfigurationError("authentication.token not specified")

        if re.search(r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*(?![A-Za-z0-9_])", token):
            expanded_token = os.path.expandvars(token)
            if re.search(
                r"\$\{[^}]+\}|\$[A-Za-z_][A-Za-z0-9_]*(?![A-Za-z0-9_])", expanded_token
            ):
                # Don't reveal the token value in error message
                raise ConfigurationError(
                    "Token configuration error: Environment variable not found"
                )
            token = expanded_token

        repo = data.get("repository")
        if not repo:
            raise ConfigurationError("repository not specified")

        cache = data.get("cache", {})
        retry = data.get("retry", {})
        logging = data.get("logging", {})
        performance = data.get("performance", {})

        return cls(
            provider=provider,
            token=token,
            repo=repo,
            base_url=data.get("base_url"),
            cache_ttl=cache.get("ttl", 300),
            max_retries=retry.get("max_attempts", 3),
            backoff_factor=retry.get("backoff_factor", 1.0),
            timeout=performance.get("timeout", 30),
            log_level=logging.get("level", "INFO"),
            log_format=logging.get("format", "json"),
            connection_pool_size=performance.get("connection_pool_size", 10),
        )
