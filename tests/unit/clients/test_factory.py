from unittest.mock import MagicMock, patch

import pytest

from drift.client import GitProvider
from drift.clients.factory import (
    ClientCreationError,
    GitClientFactory,
    UnsupportedProviderError,
)
from drift.exceptions import AuthenticationError


@pytest.fixture
def github_config():
    class MockConfig:
        def __init__(self):
            self.provider = GitProvider.GITHUB
            self.token = "ghp_" + "a" * 36
            self.repo_identifier = "owner/repo"
            self.base_url = None
            self.logger = None
            self.cache_ttl = 300
            self.cache_maxsize = 500
            self.max_retries = 3
            self.backoff_factor = 1.0
            self.per_page = 100

    return MockConfig()


@pytest.fixture
def gitlab_config():
    class MockConfig:
        def __init__(self):
            self.provider = GitProvider.GITLAB
            self.token = "glpat-" + "a" * 20
            self.repo_identifier = "123"
            self.base_url = "https://gitlab.example.com"
            self.logger = None
            self.cache_ttl = 300
            self.cache_maxsize = 500
            self.max_retries = 3
            self.backoff_factor = 1.0
            self.per_page = 100

    return MockConfig()


@pytest.fixture
def custom_config():
    class MockConfig:
        def __init__(self):
            self.provider = GitProvider.GITHUB
            self.token = "ghp_" + "b" * 36
            self.repo_identifier = "org/project"
            self.base_url = "https://github.enterprise.com"
            self.logger = MagicMock()
            self.cache_ttl = 600
            self.cache_maxsize = 1000
            self.max_retries = 5
            self.backoff_factor = 2.0
            self.per_page = 50

    return MockConfig()


@pytest.fixture
def invalid_config():
    class MockConfig:
        def __init__(self):
            self.provider = "bitbucket"
            self.token = "bitbucket_" + "d" * 20
            self.repo_identifier = "repo"
            self.base_url = None

    return MockConfig()


@patch("drift.clients.github_client.GitHubClient")
def test_should_create_github_client_when_provider_is_github(
    mock_github_client, github_config
):
    GitClientFactory.create(github_config)

    mock_github_client.assert_called_once_with(
        token="ghp_" + "a" * 36,
        repo_identifier="owner/repo",
        base_url=None,
        logger=None,
        cache_ttl=300,
        cache_maxsize=500,
        max_retries=3,
        backoff_factor=1.0,
        per_page=100,
    )


@patch("drift.clients.gitlab_client.GitLabClient")
def test_should_create_gitlab_client_when_provider_is_gitlab(
    mock_gitlab_client, gitlab_config
):
    GitClientFactory.create(gitlab_config)

    mock_gitlab_client.assert_called_once_with(
        token="glpat-" + "a" * 20,
        repo_identifier="123",
        base_url="https://gitlab.example.com",
        logger=None,
        cache_ttl=300,
        cache_maxsize=500,
        max_retries=3,
        backoff_factor=1.0,
        per_page=100,
    )


@patch("drift.clients.gitlab_client.GitLabClient")
def test_should_use_default_values_when_optional_params_not_provided(
    mock_gitlab_client,
):
    class MockConfig:
        def __init__(self):
            self.provider = GitProvider.GITLAB
            self.token = "glpat-" + "e" * 20
            self.repo_identifier = "456"
            self.base_url = None

    config = MockConfig()
    GitClientFactory.create(config)

    mock_gitlab_client.assert_called_once_with(
        token="glpat-" + "e" * 20,
        repo_identifier="456",
        base_url=None,
        logger=None,
        cache_ttl=300,
        cache_maxsize=500,
        max_retries=3,
        backoff_factor=1.0,
        per_page=100,
    )


@patch("drift.clients.github_client.GitHubClient")
def test_should_pass_custom_parameters_when_provided(mock_github_client, custom_config):
    GitClientFactory.create(custom_config)

    mock_github_client.assert_called_once_with(
        token="ghp_" + "b" * 36,
        repo_identifier="org/project",
        base_url="https://github.enterprise.com",
        logger=custom_config.logger,
        cache_ttl=600,
        cache_maxsize=1000,
        max_retries=5,
        backoff_factor=2.0,
        per_page=50,
    )


def test_should_raise_error_when_unsupported_provider_is_used(invalid_config):
    with pytest.raises(UnsupportedProviderError, match="bitbucket"):
        GitClientFactory.create(invalid_config)


@patch("drift.clients.github_client.GitHubClient")
@patch("drift.clients.gitlab_client.GitLabClient")
def test_should_only_import_required_client_when_creating(
    mock_gitlab_client, mock_github_client
):
    github_config = type(
        "Config",
        (),
        {
            "provider": GitProvider.GITHUB,
            "token": "ghp_" + "f" * 36,
            "repo_identifier": "user/repo",
            "base_url": None,
        },
    )()

    GitClientFactory.create(github_config)
    mock_github_client.assert_called_once()
    mock_gitlab_client.assert_not_called()

    mock_github_client.reset_mock()
    mock_gitlab_client.reset_mock()

    gitlab_config = type(
        "Config",
        (),
        {
            "provider": GitProvider.GITLAB,
            "token": "glpat-" + "g" * 20,
            "repo_identifier": "789",
            "base_url": None,
        },
    )()

    GitClientFactory.create(gitlab_config)
    mock_gitlab_client.assert_called_once()
    mock_github_client.assert_not_called()


def test_should_reject_empty_token():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = ""
        repo_identifier = "owner/repo"
        base_url = None

    config = MockConfig()
    with pytest.raises(AuthenticationError, match="empty token"):
        GitClientFactory.create(config)


def test_should_reject_short_token():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = "abc123"
        repo_identifier = "owner/repo"
        base_url = None

    config = MockConfig()
    with pytest.raises(AuthenticationError, match="too short"):
        GitClientFactory.create(config)


def test_should_reject_test_tokens():
    test_tokens = [
        "test" + "_" * 20,
        "example" + "_" * 20,
        "demo" + "_" * 20,
        "token" + "_" * 20,
        "fake_token" + "_" * 20,
    ]
    for test_token in test_tokens:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = test_token
            repo_identifier = "owner/repo"
            base_url = None

        config = MockConfig()
        with pytest.raises(
            AuthenticationError, match="Test/example tokens not allowed"
        ):
            GitClientFactory.create(config)


def test_should_reject_invalid_github_token_format():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = "invalid_github_token_format_1234567890"
        repo_identifier = "owner/repo"
        base_url = None

    config = MockConfig()
    with pytest.raises(AuthenticationError, match="Invalid GitHub token format"):
        GitClientFactory.create(config)


def test_should_reject_invalid_gitlab_token_format():
    class MockConfig:
        provider = GitProvider.GITLAB
        token = "invalid_gitlab_token_format_1234567890"
        repo_identifier = "123"
        base_url = None

    config = MockConfig()
    with pytest.raises(AuthenticationError, match="Invalid GitLab token format"):
        GitClientFactory.create(config)


def test_should_prevent_ssrf_with_localhost():
    dangerous_urls = [
        "http://localhost",
        "http://127.0.0.1",
        "https://0.0.0.0",
        "http://[::1]",
    ]

    for url in dangerous_urls:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = "ghp_" + "h" * 36
            repo_identifier = "owner/repo"
            base_url = url

        config = MockConfig()
        with pytest.raises(ValueError, match="not allowed for security reasons"):
            GitClientFactory.create(config)


def test_should_prevent_ssrf_with_private_networks():
    dangerous_urls = [
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://172.16.0.1",
        "http://172.31.255.255",
        "http://169.254.169.254",
    ]

    for url in dangerous_urls:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = "ghp_" + "i" * 36
            repo_identifier = "owner/repo"
            base_url = url

        config = MockConfig()
        with pytest.raises(ValueError, match="not allowed"):
            GitClientFactory.create(config)


def test_should_reject_invalid_url_schemes():
    dangerous_urls = [
        "file:///etc/passwd",
        "gopher://example.com",
        "ftp://example.com",
        "javascript:alert(1)",
    ]

    for url in dangerous_urls:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = "ghp_" + "j" * 36
            repo_identifier = "owner/repo"
            base_url = url

        config = MockConfig()
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            GitClientFactory.create(config)


def test_should_reject_malformed_repo_identifiers():
    dangerous_identifiers = [
        "../../../etc/passwd",
        "owner/repo; rm -rf /",
        "owner/repo && curl evil.com",
        "owner/repo\n\nmalicious",
        "owner//repo",
        "owner\\repo",
        "owner|repo",
        "owner&repo",
        "owner$repo",
    ]

    for identifier in dangerous_identifiers:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = "ghp_" + "k" * 36
            repo_identifier = identifier
            base_url = None

        config = MockConfig()
        with pytest.raises(ValueError, match="Invalid"):
            GitClientFactory.create(config)


def test_should_reject_empty_repo_identifier():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = "ghp_" + "l" * 36
        repo_identifier = ""
        base_url = None

    config = MockConfig()
    with pytest.raises(ValueError, match="cannot be empty"):
        GitClientFactory.create(config)


def test_should_validate_numeric_bounds():
    test_cases = [
        ("cache_ttl", -1, "cache_ttl out of bounds"),
        ("cache_ttl", 100000, "cache_ttl out of bounds"),
        ("cache_maxsize", -1, "cache_maxsize out of bounds"),
        ("cache_maxsize", 20000, "cache_maxsize out of bounds"),
        ("max_retries", -1, "max_retries out of bounds"),
        ("max_retries", 20, "max_retries out of bounds"),
        ("backoff_factor", -1.0, "backoff_factor out of bounds"),
        ("backoff_factor", 10.0, "backoff_factor out of bounds"),
        ("per_page", 0, "per_page out of bounds"),
        ("per_page", 200, "per_page out of bounds"),
    ]

    for param_name, value, expected_message in test_cases:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = "ghp_" + "m" * 36
            repo_identifier = "owner/repo"
            base_url = None

        setattr(MockConfig, param_name, value)
        config = MockConfig()

        with pytest.raises(ValueError, match=expected_message):
            GitClientFactory.create(config)


def test_should_accept_valid_gitlab_project_formats():
    valid_identifiers = ["123", "456789", "namespace/project", "group/subgroup-project"]

    for identifier in valid_identifiers:

        class MockConfig:
            provider = GitProvider.GITLAB
            token = "glpat-" + "n" * 20
            repo_identifier = identifier
            base_url = None

        config = MockConfig()

        with patch("drift.clients.gitlab_client.GitLabClient"):
            GitClientFactory.create(config)


def test_should_handle_import_error_gracefully():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = "ghp_" + "o" * 36
        repo_identifier = "owner/repo"
        base_url = None

    config = MockConfig()

    with patch.dict("sys.modules", {"drift.clients.github_client": None}):
        with pytest.raises(ClientCreationError, match="Failed to import"):
            GitClientFactory.create(config)


def test_should_handle_client_initialization_error():
    class MockConfig:
        provider = GitProvider.GITHUB
        token = "ghp_" + "p" * 36
        repo_identifier = "owner/repo"
        base_url = None

    config = MockConfig()

    with patch("drift.clients.github_client.GitHubClient") as mock_client:
        mock_client.side_effect = Exception("Connection failed")
        with pytest.raises(ClientCreationError, match="Failed to create"):
            GitClientFactory.create(config)


def test_should_accept_various_valid_token_formats():
    github_tokens = [
        "ghp_" + "a" * 36,
        "github_pat_" + "b" * 22 + "_" + "c" * 59,
    ]

    gitlab_tokens = [
        "glpat-" + "a" * 20,
        "glpat-" + "b" * 30,
        "glprt-" + "c" * 20,
        "glprt-" + "d" * 25,
    ]

    for gh_token in github_tokens:

        class MockConfig:
            provider = GitProvider.GITHUB
            token = gh_token
            repo_identifier = "owner/repo"
            base_url = None

        config = MockConfig()
        with patch("drift.clients.github_client.GitHubClient"):
            GitClientFactory.create(config)

    for gl_token in gitlab_tokens:

        class MockConfig:
            provider = GitProvider.GITLAB
            token = gl_token
            repo_identifier = "123"
            base_url = None

        config = MockConfig()
        with patch("drift.clients.gitlab_client.GitLabClient"):
            GitClientFactory.create(config)
