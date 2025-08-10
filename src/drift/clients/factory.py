import re
from typing import Any, Protocol
from urllib.parse import urlparse

from drift.client import GitClient, GitProvider
from drift.exceptions import AuthenticationError


class ClientConfig(Protocol):
    @property
    def provider(self) -> GitProvider: ...
    @property
    def token(self) -> str: ...
    @property
    def repo_identifier(self) -> str: ...
    @property
    def base_url(self) -> str | None: ...
    @property
    def logger(self) -> Any | None: ...
    @property
    def cache_ttl(self) -> int: ...
    @property
    def cache_maxsize(self) -> int: ...
    @property
    def max_retries(self) -> int: ...
    @property
    def backoff_factor(self) -> float: ...
    @property
    def per_page(self) -> int: ...


class UnsupportedProviderError(Exception):
    def __init__(self, provider: str, supported: list[str]):
        self.provider = provider
        self.supported = supported
        super().__init__(
            f"Provider '{provider}' is not supported. "
            f"Supported providers: {', '.join(supported)}"
        )


class ClientCreationError(Exception):
    pass


class GitClientFactory:
    _REPO_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$")
    _GITLAB_ID_PATTERN = re.compile(r"^\d+$")
    _GITHUB_TOKEN_PATTERNS = [
        re.compile(r"^ghp_[a-zA-Z0-9]{36}$"),
        re.compile(r"^github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}$"),
    ]
    _GITLAB_TOKEN_PATTERNS = [
        re.compile(r"^glpat-[a-zA-Z0-9_\-]{20,}$"),
        re.compile(r"^glprt-[a-zA-Z0-9_\-]{20,}$"),
    ]
    _DEFAULT_CONFIG = {
        "logger": None,
        "cache_ttl": 300,
        "cache_maxsize": 500,
        "max_retries": 3,
        "backoff_factor": 1.0,
        "per_page": 100,
    }
    _FORBIDDEN_HOSTS = {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",  # nosec B104 - Used for SSRF prevention, not binding
        "169.254.169.254",
        "::1",
        "[::1]",
    }

    @staticmethod
    def _validate_token(token: str, provider: GitProvider) -> None:
        if not token:
            raise AuthenticationError("Invalid token: empty token")

        token_lower = token.lower()
        for test_pattern in ["test", "example", "demo", "token", "fake_token"]:
            if token_lower.startswith(test_pattern):
                raise AuthenticationError(
                    "Test/example tokens not allowed in production"
                )

        if len(token) < 20:
            raise AuthenticationError("Invalid token: too short")

        if provider == GitProvider.GITHUB:
            patterns = GitClientFactory._GITHUB_TOKEN_PATTERNS
            if not any(pattern.match(token) for pattern in patterns):
                if not token.startswith(("ghp_", "github_pat_")):
                    raise AuthenticationError(
                        "Invalid GitHub token format. "
                        "Expected format: ghp_* or github_pat_*"
                    )
        elif provider == GitProvider.GITLAB:
            patterns = GitClientFactory._GITLAB_TOKEN_PATTERNS
            if not any(pattern.match(token) for pattern in patterns):
                if not token.startswith(("glpat-", "glprt-")):
                    raise AuthenticationError(
                        "Invalid GitLab token format. "
                        "Expected format: glpat-* or glprt-*"
                    )

    @staticmethod
    def _validate_repo_identifier(repo_identifier: str, provider: GitProvider) -> None:
        if not repo_identifier:
            raise ValueError("repo_identifier cannot be empty")

        dangerous_patterns = ["../", "..", "//", "\\", "\n", "\r", ";", "&", "|", "$"]
        for pattern in dangerous_patterns:
            if pattern in repo_identifier:
                raise ValueError(
                    f"Invalid repo_identifier: contains dangerous pattern '{pattern}'"
                )

        if provider == GitProvider.GITHUB:
            if not GitClientFactory._REPO_PATTERN.match(repo_identifier):
                raise ValueError(
                    f"Invalid GitHub repo format: {repo_identifier}. "
                    f"Expected format: owner/repo"
                )
        elif provider == GitProvider.GITLAB:
            if not GitClientFactory._GITLAB_ID_PATTERN.match(repo_identifier):
                if not GitClientFactory._REPO_PATTERN.match(repo_identifier):
                    raise ValueError(
                        f"Invalid GitLab project identifier: {repo_identifier}. "
                        f"Expected format: numeric ID or namespace/project"
                    )

    @staticmethod
    def _validate_base_url(base_url: str | None) -> None:
        if not base_url:
            return

        try:
            parsed = urlparse(base_url)

            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}")

            if not parsed.netloc:
                raise ValueError("Invalid URL: missing host")

            hostname = parsed.hostname
            if hostname and hostname.lower() in GitClientFactory._FORBIDDEN_HOSTS:
                raise ValueError(
                    f"Access to host '{hostname}' is not allowed for security reasons"
                )

            if hostname and hostname.startswith("10."):
                raise ValueError("Access to private network (10.x.x.x) not allowed")
            if hostname and hostname.startswith("192.168."):
                raise ValueError("Access to private network (192.168.x.x) not allowed")
            if hostname and hostname.startswith("172."):
                octets = hostname.split(".")
                if len(octets) >= 2 and 16 <= int(octets[1]) <= 31:
                    raise ValueError(
                        "Access to private network (172.16-31.x.x) not allowed"
                    )

        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Invalid base_url: {e}") from e

    @staticmethod
    def _validate_numeric_params(config: ClientConfig) -> None:
        if hasattr(config, "cache_ttl"):
            cache_ttl = getattr(config, "cache_ttl", 300)
            if not (0 <= cache_ttl <= 86400):
                raise ValueError(
                    f"cache_ttl out of bounds: {cache_ttl}. Must be between 0 and 86400"
                )

        if hasattr(config, "cache_maxsize"):
            cache_maxsize = getattr(config, "cache_maxsize", 500)
            if not (0 <= cache_maxsize <= 10000):
                raise ValueError(
                    f"cache_maxsize out of bounds: {cache_maxsize}. "
                    f"Must be between 0 and 10000"
                )

        if hasattr(config, "max_retries"):
            max_retries = getattr(config, "max_retries", 3)
            if not (0 <= max_retries <= 10):
                raise ValueError(
                    f"max_retries out of bounds: {max_retries}. "
                    f"Must be between 0 and 10"
                )

        if hasattr(config, "backoff_factor"):
            backoff_factor = getattr(config, "backoff_factor", 1.0)
            if not (0.0 <= backoff_factor <= 5.0):
                raise ValueError(
                    f"backoff_factor out of bounds: {backoff_factor}. "
                    f"Must be between 0.0 and 5.0"
                )

        if hasattr(config, "per_page"):
            per_page = getattr(config, "per_page", 100)
            if not (1 <= per_page <= 100):
                raise ValueError(
                    f"per_page out of bounds: {per_page}. Must be between 1 and 100"
                )

    @staticmethod
    def _extract_config(config: ClientConfig) -> dict[str, Any]:
        return {
            "token": config.token,
            "repo_identifier": config.repo_identifier,
            "base_url": config.base_url,
            **{
                key: getattr(config, key, default)
                for key, default in GitClientFactory._DEFAULT_CONFIG.items()
            },
        }

    @staticmethod
    def _validate_config(config: ClientConfig) -> None:
        GitClientFactory._validate_token(config.token, config.provider)
        GitClientFactory._validate_repo_identifier(
            config.repo_identifier, config.provider
        )
        GitClientFactory._validate_base_url(config.base_url)
        GitClientFactory._validate_numeric_params(config)

    @staticmethod
    def create(config: ClientConfig) -> GitClient:
        GitClientFactory._validate_config(config)

        params = GitClientFactory._extract_config(config)

        try:
            if config.provider == GitProvider.GITHUB:
                from drift.clients.github_client import GitHubClient

                return GitHubClient(**params)
            elif config.provider == GitProvider.GITLAB:
                from drift.clients.gitlab_client import GitLabClient

                return GitLabClient(**params)

            supported = [p.value for p in GitProvider]  # type: ignore[unreachable]
            raise UnsupportedProviderError(str(config.provider), supported)
        except ImportError as e:
            raise ClientCreationError(
                f"Failed to import {config.provider} client: {e}. "
                f"Ensure the required dependencies are installed."
            ) from e
        except (UnsupportedProviderError, AuthenticationError, ValueError):
            raise
        except Exception as e:
            raise ClientCreationError(
                f"Failed to create {config.provider} client: {e}"
            ) from e
