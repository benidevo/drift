from unittest.mock import MagicMock, patch

import pytest

from drift.app import ConfigAdapter, DriftApplication
from drift.client import GitProvider
from drift.config import DriftConfig
from drift.models import Comment, DiffData, PullRequestInfo


@pytest.fixture
def drift_config():
    return DriftConfig(
        provider=GitProvider.GITHUB,
        token="ghp_" + "x" * 36,
        repo="owner/repo",
        base_url=None,
        cache_ttl=300,
        max_retries=3,
        backoff_factor=1.0,
        timeout=30,
        log_level="INFO",
        log_format="json",
        connection_pool_size=10,
    )


@pytest.fixture
def config_adapter(drift_config):
    return ConfigAdapter(drift_config)


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_pr_info.return_value = MagicMock(spec=PullRequestInfo)
    client.get_diff_data.return_value = MagicMock(spec=DiffData)
    client.get_commit_messages.return_value = ["feat: add feature", "fix: bug fix"]
    client.get_existing_comments.return_value = [MagicMock(spec=Comment)]
    return client


def test_should_adapt_drift_config_to_client_config(config_adapter, drift_config):
    assert config_adapter.provider == drift_config.provider
    assert config_adapter.token == drift_config.token
    assert config_adapter.repo_identifier == drift_config.repo
    assert config_adapter.base_url == drift_config.base_url
    assert config_adapter.cache_ttl == drift_config.cache_ttl
    assert config_adapter.max_retries == drift_config.max_retries
    assert config_adapter.backoff_factor == drift_config.backoff_factor


def test_should_provide_default_values_for_missing_config(config_adapter):
    assert config_adapter.cache_maxsize == 500
    assert config_adapter.per_page == 100


def test_should_create_logger_from_config(config_adapter, drift_config):
    logger = config_adapter.logger
    assert logger is not None
    assert logger.name == "drift"


@patch("drift.app.GitClientFactory")
def test_should_create_client_using_factory(mock_factory, drift_config):
    mock_client = MagicMock()
    mock_factory.create.return_value = mock_client

    app = DriftApplication(drift_config)
    client = app.client

    assert client == mock_client
    mock_factory.create.assert_called_once()

    # Should reuse the same client on subsequent calls
    client2 = app.client
    assert client2 == mock_client
    assert mock_factory.create.call_count == 1


@patch("drift.app.DriftConfig")
def test_should_create_app_from_env(mock_config_class):
    mock_config = MagicMock()
    mock_config_class.from_env.return_value = mock_config

    app = DriftApplication.from_env()

    assert app.config == mock_config
    mock_config_class.from_env.assert_called_once()


@patch("drift.app.DriftConfig")
def test_should_create_app_from_file(mock_config_class):
    mock_config = MagicMock()
    mock_config_class.from_file.return_value = mock_config

    app = DriftApplication.from_file("/path/to/config.yaml")

    assert app.config == mock_config
    mock_config_class.from_file.assert_called_once_with("/path/to/config.yaml")


@patch("drift.app.GitClientFactory")
def test_should_analyze_pr(mock_factory, drift_config, mock_client):
    mock_factory.create.return_value = mock_client

    app = DriftApplication(drift_config)
    result = app.analyze_pr("123")

    assert "pr_info" in result
    assert "diff_data" in result
    assert "commits" in result
    assert "comments" in result

    mock_client.get_pr_info.assert_called_once_with("123")
    mock_client.get_diff_data.assert_called_once_with("123")
    mock_client.get_commit_messages.assert_called_once_with("123")
    mock_client.get_existing_comments.assert_called_once_with("123")


@patch("drift.app.GitClientFactory")
def test_should_post_review(mock_factory, drift_config, mock_client):
    mock_factory.create.return_value = mock_client

    app = DriftApplication(drift_config)
    app.post_review("123", "Great work!")

    mock_client.post_comment.assert_called_once_with("123", "Great work!")


@patch("drift.app.GitClientFactory")
def test_should_update_review(mock_factory, drift_config, mock_client):
    mock_factory.create.return_value = mock_client

    app = DriftApplication(drift_config)
    app.update_review("123", "comment-456", "Updated: Great work!")

    mock_client.update_comment.assert_called_once_with(
        "123", "comment-456", "Updated: Great work!"
    )
