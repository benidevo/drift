import os
import tempfile
from unittest.mock import patch

import pytest
import yaml

from drift.config import DriftConfig
from drift.exceptions import ConfigurationError


def test_should_raise_error_when_env_vars_contain_invalid_numbers() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "GITHUB_TOKEN": "test_token",
        "DRIFT_REPO": "owner/repo",
    }

    # Test invalid integer in DRIFT_CACHE_TTL
    env_vars["DRIFT_CACHE_TTL"] = "not-a-number"
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="Invalid integer value for DRIFT_CACHE_TTL"
        ):
            DriftConfig.from_env()

    # Test invalid integer in DRIFT_MAX_RETRIES
    env_vars["DRIFT_CACHE_TTL"] = "300"
    env_vars["DRIFT_MAX_RETRIES"] = "3.14"  # Float when expecting int
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="Invalid integer value for DRIFT_MAX_RETRIES"
        ):
            DriftConfig.from_env()

    # Test invalid float in DRIFT_BACKOFF_FACTOR
    env_vars["DRIFT_MAX_RETRIES"] = "3"
    env_vars["DRIFT_BACKOFF_FACTOR"] = "not.a.float"
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="Invalid float value for DRIFT_BACKOFF_FACTOR"
        ):
            DriftConfig.from_env()

    # Test invalid integer in DRIFT_TIMEOUT
    env_vars["DRIFT_BACKOFF_FACTOR"] = "1.0"
    env_vars["DRIFT_TIMEOUT"] = "30s"  # Has unit suffix
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError, match="Invalid integer value for DRIFT_TIMEOUT"
        ):
            DriftConfig.from_env()

    # Test invalid integer in DRIFT_CONNECTION_POOL_SIZE
    env_vars["DRIFT_TIMEOUT"] = "30"
    env_vars["DRIFT_CONNECTION_POOL_SIZE"] = "ten"
    with patch.dict(os.environ, env_vars, clear=True):
        with pytest.raises(
            ConfigurationError,
            match="Invalid integer value for DRIFT_CONNECTION_POOL_SIZE",
        ):
            DriftConfig.from_env()


def test_should_use_defaults_when_env_vars_are_empty_strings() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "GITHUB_TOKEN": "test_token",
        "DRIFT_REPO": "owner/repo",
        "DRIFT_CACHE_TTL": "",  # Empty string should use default
        "DRIFT_MAX_RETRIES": "",
        "DRIFT_BACKOFF_FACTOR": "",
        "DRIFT_TIMEOUT": "",
        "DRIFT_CONNECTION_POOL_SIZE": "",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        config = DriftConfig.from_env()

    # Should use all defaults
    assert config.cache_ttl == 300
    assert config.max_retries == 3
    assert config.backoff_factor == 1.0
    assert config.timeout == 30
    assert config.connection_pool_size == 10


def test_should_detect_unexpanded_env_vars_in_token() -> None:
    config_data = {
        "provider": "github",
        "repository": "owner/repo",
        "authentication": {"token": "${UNDEFINED_TOKEN}"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        yaml.dump(config_data, tmp)
        tmp_path = tmp.name

    try:
        # Undefined variable should be detected
        with pytest.raises(
            ConfigurationError,
            match="Token configuration error: Environment variable not found",
        ):
            DriftConfig.from_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    # Test with partially expanded variable
    config_data["authentication"]["token"] = "prefix_${UNDEFINED}_suffix"

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        yaml.dump(config_data, tmp)
        tmp_path = tmp.name

    try:
        with pytest.raises(
            ConfigurationError,
            match="Token configuration error: Environment variable not found",
        ):
            DriftConfig.from_file(tmp_path)
    finally:
        os.unlink(tmp_path)


def test_should_handle_special_characters_in_expanded_token() -> None:
    config_data = {
        "provider": "github",
        "repository": "owner/repo",
        "authentication": {"token": "${SPECIAL_TOKEN}"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
        yaml.dump(config_data, tmp)
        tmp_path = tmp.name

    try:
        # Test with token containing special characters
        special_token = "ghp_abc123!@#$%^&*()_+-=[]{}|;:',.<>?/~`"
        with patch.dict(os.environ, {"SPECIAL_TOKEN": special_token}):
            config = DriftConfig.from_file(tmp_path)
            assert config.token == special_token
    finally:
        os.unlink(tmp_path)


def test_should_handle_edge_case_numeric_values() -> None:
    env_vars = {
        "DRIFT_PROVIDER": "github",
        "GITHUB_TOKEN": "test_token",
        "DRIFT_REPO": "owner/repo",
        "DRIFT_CACHE_TTL": "0",  # Zero should be valid
        "DRIFT_MAX_RETRIES": "0",  # Zero retries
        "DRIFT_BACKOFF_FACTOR": "0.0",  # Zero backoff
        "DRIFT_TIMEOUT": "1",  # Minimum positive
        "DRIFT_CONNECTION_POOL_SIZE": "1",  # Minimum positive
    }

    with patch.dict(os.environ, env_vars, clear=True):
        config = DriftConfig.from_env()

    assert config.cache_ttl == 0
    assert config.max_retries == 0
    assert config.backoff_factor == 0.0
    assert config.timeout == 1
    assert config.connection_pool_size == 1

    # Test large values
    env_vars["DRIFT_CACHE_TTL"] = "86400"  # 24 hours
    env_vars["DRIFT_MAX_RETRIES"] = "100"
    env_vars["DRIFT_BACKOFF_FACTOR"] = "10.5"
    env_vars["DRIFT_TIMEOUT"] = "3600"  # 1 hour
    env_vars["DRIFT_CONNECTION_POOL_SIZE"] = "1000"

    with patch.dict(os.environ, env_vars, clear=True):
        config = DriftConfig.from_env()

    assert config.cache_ttl == 86400
    assert config.max_retries == 100
    assert config.backoff_factor == 10.5
    assert config.timeout == 3600
    assert config.connection_pool_size == 1000
