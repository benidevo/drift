from pathlib import Path
import tempfile

import pytest

from drift.exceptions import ConfigurationError, SecurityError
from drift.security import SecurityValidator


def test_should_reject_empty_config_path():
    with pytest.raises(ConfigurationError, match="Config path cannot be empty"):
        SecurityValidator.validate_config_path("")


def test_should_reject_nonexistent_config_file():
    with pytest.raises(ConfigurationError, match="Config file not found"):
        SecurityValidator.validate_config_path("/nonexistent/file.yaml")


def test_should_reject_directory_as_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ConfigurationError, match="must be a file, not a directory"):
            SecurityValidator.validate_config_path(tmpdir)


def test_should_reject_invalid_config_extension():
    with tempfile.NamedTemporaryFile(suffix=".txt") as tmpfile:
        with pytest.raises(ConfigurationError, match="must be .yaml, .yml, or .json"):
            SecurityValidator.validate_config_path(tmpfile.name)


def test_should_reject_large_config_file():
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmpfile:
        tmpfile.write(b"x" * (1024 * 1024 + 1))
        tmpfile.flush()
        with pytest.raises(ConfigurationError, match="Config file too large"):
            SecurityValidator.validate_config_path(tmpfile.name)


def test_should_accept_valid_config_file():
    with tempfile.NamedTemporaryFile(suffix=".yaml") as tmpfile:
        tmpfile.write(b"provider: github\n")
        tmpfile.flush()
        result = SecurityValidator.validate_config_path(tmpfile.name)
        assert isinstance(result, Path)
        assert result.exists()


def test_should_reject_empty_output_path():
    with pytest.raises(ValueError, match="Output path cannot be empty"):
        SecurityValidator.validate_output_path("")


def test_should_reject_system_directories():
    dangerous_paths = [
        "/etc/passwd",
        "/sys/something",
        "/proc/self/environ",
        "/boot/grub/grub.cfg",
        "/dev/null",
        "/root/.bashrc",
    ]
    for path in dangerous_paths:
        with pytest.raises(SecurityError):
            SecurityValidator.validate_output_path(path)


def test_should_reject_sensitive_files():
    dangerous_paths = [
        "~/.ssh/authorized_keys",
        "/home/user/.ssh/id_rsa",
        "~/.bashrc",
        "~/.gitconfig",
        "/etc/sudoers",
    ]
    for path in dangerous_paths:
        with pytest.raises(SecurityError, match="Cannot overwrite sensitive file"):
            SecurityValidator.validate_output_path(path)


def test_should_accept_valid_output_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "output.json"
        result = SecurityValidator.validate_output_path(str(output_path))
        assert isinstance(result, Path)
        assert result.parent.exists()


def test_should_reject_empty_pr_id():
    with pytest.raises(ValueError, match="PR ID cannot be empty"):
        SecurityValidator.validate_pr_id("")


def test_should_reject_non_numeric_pr_id():
    invalid_ids = ["abc", "12a", "PR-123", "123.45"]
    for pr_id in invalid_ids:
        with pytest.raises(ValueError, match="Invalid PR ID format"):
            SecurityValidator.validate_pr_id(pr_id)


def test_should_reject_out_of_range_pr_id():
    invalid_ids = ["0", "-1", "2147483648", "999999999999"]
    for pr_id in invalid_ids:
        with pytest.raises(ValueError, match="PR ID out of valid range"):
            SecurityValidator.validate_pr_id(pr_id)


def test_should_accept_valid_pr_id():
    valid_ids = ["1", "123", "999999", "2147483647"]
    for pr_id in valid_ids:
        result = SecurityValidator.validate_pr_id(pr_id)
        assert result == pr_id.strip()


def test_should_strip_whitespace_from_pr_id():
    result = SecurityValidator.validate_pr_id("  123  ")
    assert result == "123"


def test_should_reject_empty_comment_id():
    with pytest.raises(ValueError, match="Comment ID cannot be empty"):
        SecurityValidator.validate_comment_id("")


def test_should_reject_invalid_comment_id_format():
    invalid_ids = ["comment@123", "id#456", "comment/789", "id\\123"]
    for comment_id in invalid_ids:
        with pytest.raises(ValueError, match="Invalid comment ID format"):
            SecurityValidator.validate_comment_id(comment_id)


def test_should_reject_too_long_comment_id():
    long_id = "a" * 101
    with pytest.raises(ValueError, match="Comment ID too long"):
        SecurityValidator.validate_comment_id(long_id)


def test_should_accept_valid_comment_id():
    valid_ids = ["comment-123", "id_456", "ABC123", "comment_123_abc"]
    for comment_id in valid_ids:
        result = SecurityValidator.validate_comment_id(comment_id)
        assert result == comment_id.strip()


def test_should_sanitize_github_tokens():
    text = "Token is ghp_abcd1234567890abcd1234567890abcd1234"
    sanitized = SecurityValidator.sanitize_for_logging(text)
    assert "ghp_[REDACTED]" in sanitized
    assert "ghp_abcd" not in sanitized


def test_should_sanitize_gitlab_tokens():
    text = "Using token glpat-1234567890abcdefghij"
    sanitized = SecurityValidator.sanitize_for_logging(text)
    assert "glpat-[REDACTED]" in sanitized
    assert "1234567890" not in sanitized


def test_should_sanitize_generic_secrets():
    text = "password=secret123 token=abc456 api_key=xyz789"
    sanitized = SecurityValidator.sanitize_for_logging(text)
    assert "password=[REDACTED]" in sanitized
    assert "token=[REDACTED]" in sanitized
    assert "api_key=[REDACTED]" in sanitized
    assert "secret123" not in sanitized


def test_should_sanitize_headers():
    text = "Authorization: Bearer abc123 X-Api-Key: xyz456"
    sanitized = SecurityValidator.sanitize_for_logging(text)
    assert "Authorization: [REDACTED]" in sanitized
    assert "X-Api-Key: [REDACTED]" in sanitized
    assert "abc123" not in sanitized


def test_should_sanitize_error_messages():
    error = Exception("Failed to connect with token ghp_secret123")
    sanitized = SecurityValidator.sanitize_error_message(error)
    assert "ghp_[REDACTED]" in sanitized
    assert "ghp_secret123" not in sanitized


def test_should_remove_file_paths_from_errors():
    error = Exception("File not found: /home/user/project/config.yaml")
    sanitized = SecurityValidator.sanitize_error_message(error)
    assert "/home/user" not in sanitized
    assert "config.yaml" in sanitized
