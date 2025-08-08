import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from drift.client import GitProvider
from drift.config import DriftConfig
from drift.exceptions import ConfigurationError


def test_should_create_config_when_all_env_vars_are_set() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "GITHUB_TOKEN": "ghp_test_token",
        "DRIFT_REPO": "owner/repo",
        "GITHUB_BASE_URL": "https://github.enterprise.com",
        "DRIFT_CACHE_TTL": "600",
        "DRIFT_MAX_RETRIES": "5",
        "DRIFT_TIMEOUT": "60",
        "DRIFT_LOG_LEVEL": "DEBUG",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        config = DriftConfig.from_env()

    assert config.provider == GitProvider.GITHUB
    assert config.token == "ghp_test_token"
    assert config.repo == "owner/repo"
    assert config.base_url == "https://github.enterprise.com"
    assert config.cache_ttl == 600
    assert config.max_retries == 5
    assert config.timeout == 60
    assert config.log_level == "DEBUG"


def test_should_create_gitlab_config_when_gitlab_env_vars_are_set() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "gitlab",
        "GITLAB_TOKEN": "glpat_test_token",
        "DRIFT_REPO": "group/project",
        "GITLAB_URL": "https://gitlab.self-hosted.com",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        config = DriftConfig.from_env()

    assert config.provider == GitProvider.GITLAB
    assert config.token == "glpat_test_token"
    assert config.repo == "group/project"
    assert config.base_url == "https://gitlab.self-hosted.com"


def test_should_raise_error_when_provider_env_var_is_missing() -> None:
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(
            ConfigurationError, match="DRIFT_PROVIDER environment variable not set"
        ):
            DriftConfig.from_env()


def test_should_raise_error_when_provider_is_invalid() -> None:
    env_vars = {"DRIFT_PROVIDER": "bitbucket"}

    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(ConfigurationError, match="Invalid provider"):
            DriftConfig.from_env()


def test_should_raise_error_when_token_env_var_is_missing() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "DRIFT_REPO": "owner/repo",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="GITHUB_TOKEN environment variable not set"
        ):
            DriftConfig.from_env()


def test_should_raise_error_when_repo_env_var_is_missing() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "GITHUB_TOKEN": "test_token",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="DRIFT_REPO environment variable not set"
        ):
            DriftConfig.from_env()


def test_should_load_config_when_yaml_file_is_valid() -> None:
    config_data = {
        "provider": "github",
        "repository": "owner/repo",
        "authentication": {"token": "test_token"},
        "cache": {"ttl": 600},
        "retry": {"max_attempts": 5, "backoff_factor": 2.0},
        "logging": {"level": "DEBUG", "format": "plain"},
        "performance": {"timeout": 60, "connection_pool_size": 20},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        yaml.dump(config_data, tmp)
        tmp_path = tmp.name

    try:
        config = DriftConfig.from_file(tmp_path)

        assert config.provider == GitProvider.GITHUB
        assert config.token == "test_token"
        assert config.repo == "owner/repo"
        assert config.cache_ttl == 600
        assert config.max_retries == 5
        assert config.backoff_factor == 2.0
        assert config.timeout == 60
        assert config.log_level == "DEBUG"
        assert config.log_format == "plain"
        assert config.connection_pool_size == 20
    finally:
        os.unlink(tmp_path)


def test_should_expand_env_vars_when_config_contains_placeholders() -> None:
    config_data = {
        "provider": "github",
        "repository": "owner/repo",
        "authentication": {"token": "${TEST_TOKEN}"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        yaml.dump(config_data, tmp)
        tmp_path = tmp.name

    try:
        with patch.dict(os.environ, {"TEST_TOKEN": "expanded_token"}):
            config = DriftConfig.from_file(tmp_path)

        assert config.token == "expanded_token"
    finally:
        os.unlink(tmp_path)


def test_should_raise_error_when_config_file_does_not_exist() -> None:
    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        DriftConfig.from_file("/nonexistent/config.yml")


def test_should_raise_error_when_yaml_is_invalid() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        tmp.write("invalid: yaml: content: [")
        tmp_path = tmp.name

    try:
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            DriftConfig.from_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_should_raise_error_when_config_file_is_empty() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with pytest.raises(ConfigurationError, match="Configuration file is empty"):
            DriftConfig.from_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_should_validate_when_all_required_fields_are_valid() -> None:
    config = DriftConfig(
        provider=GitProvider.GITHUB,
        token="test_token",
        repo="owner/repo",
        cache_ttl=300,
        max_retries=3,
        backoff_factor=1.0,
        timeout=30,
        connection_pool_size=10,
    )

    assert config.token == "test_token"
    assert config.repo == "owner/repo"


def test_should_raise_error_when_token_is_empty() -> None:
    with pytest.raises(ConfigurationError, match="Token is required"):
        DriftConfig(
            provider=GitProvider.GITHUB,
            token="",
            repo="owner/repo",
        )


def test_should_raise_error_when_repo_is_empty() -> None:
    with pytest.raises(ConfigurationError, match="Repository is required"):
        DriftConfig(
            provider=GitProvider.GITHUB,
            token="test_token",
            repo="",
        )


def test_should_raise_error_when_cache_ttl_is_negative() -> None:
    with pytest.raises(ConfigurationError, match="cache_ttl must be non-negative"):
        DriftConfig(
            provider=GitProvider.GITHUB,
            token="test_token",
            repo="owner/repo",
            cache_ttl=-1,
        )


def test_should_raise_error_when_timeout_is_zero() -> None:
    with pytest.raises(ConfigurationError, match="timeout must be positive"):
        DriftConfig(
            provider=GitProvider.GITHUB,
            token="test_token",
            repo="owner/repo",
            timeout=0,
        )
