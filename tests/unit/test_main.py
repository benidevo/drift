import json
import logging
from unittest.mock import MagicMock, patch

from drift.__main__ import main, setup_logging


def test_should_setup_json_logging(caplog):
    with caplog.at_level(logging.INFO):
        setup_logging("INFO", "json")
        logger = logging.getLogger(__name__)
        logger.info("Test message")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "INFO"
    assert record.message == "Test message"


def test_should_setup_text_logging(caplog):
    with caplog.at_level(logging.DEBUG):
        setup_logging("DEBUG", "text")
        logger = logging.getLogger(__name__)
        logger.debug("Debug message")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelname == "DEBUG"


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "test"])
def test_should_test_configuration_from_env(mock_app_class):
    mock_app = MagicMock()
    mock_app.config.provider = "github"
    mock_app.config.repo = "owner/repo"
    mock_app.config.base_url = None
    mock_app.client = MagicMock()
    mock_app.client.__class__.__name__ = "GitHubClient"
    mock_app_class.from_env.return_value = mock_app

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_app_class.from_env.assert_called_once()


@patch("drift.__main__.SecurityValidator")
@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "--config", "config.yaml", "test"])
def test_should_test_configuration_from_file(mock_app_class, mock_validator):
    mock_app = MagicMock()
    mock_app.config.provider = "gitlab"
    mock_app.config.repo = "123"
    mock_app.config.base_url = "https://gitlab.com"
    mock_app.client = MagicMock()
    mock_app.client.__class__.__name__ = "GitLabClient"
    mock_app_class.from_file.return_value = mock_app

    from pathlib import Path

    mock_validator.validate_config_path.return_value = Path("config.yaml")

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_validator.validate_config_path.assert_called_once_with("config.yaml")
    mock_app_class.from_file.assert_called_once_with("config.yaml")


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "analyze", "123"])
def test_should_analyze_pr(mock_app_class, capsys):
    mock_app = MagicMock()
    mock_app.analyze_pr.return_value = {
        "pr_info": {"title": "Test PR"},
        "diff_data": {"files": []},
        "commits": [],
        "comments": [],
    }
    mock_app_class.from_env.return_value = mock_app

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_app.analyze_pr.assert_called_once_with("123")
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["pr_info"]["title"] == "Test PR"


@patch("drift.__main__.SecurityValidator")
@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "analyze", "123", "--output", "analysis.json"])
def test_should_analyze_pr_with_output_file(mock_app_class, mock_validator):
    mock_app = MagicMock()
    mock_app.analyze_pr.return_value = {
        "pr_info": {"title": "Test PR"},
        "diff_data": {"files": []},
        "commits": [],
        "comments": [],
    }
    mock_app_class.from_env.return_value = mock_app

    from pathlib import Path

    mock_path = MagicMock(spec=Path)
    mock_validator.validate_pr_id.return_value = "123"
    mock_validator.validate_output_path.return_value = mock_path

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_validator.validate_output_path.assert_called_once_with("analysis.json")
    mock_path.write_text.assert_called_once()
    mock_path.chmod.assert_called_once_with(0o644)
    written_data = json.loads(mock_path.write_text.call_args[0][0])
    assert written_data["pr_info"]["title"] == "Test PR"


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "comment", "123", "Great work!"])
def test_should_post_comment(mock_app_class):
    mock_app = MagicMock()
    mock_app_class.from_env.return_value = mock_app

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_app.post_review.assert_called_once_with("123", "Great work!")


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "update", "123", "comment-456", "Updated comment"])
def test_should_update_comment(mock_app_class):
    mock_app = MagicMock()
    mock_app_class.from_env.return_value = mock_app

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_not_called()

    mock_app.update_review.assert_called_once_with(
        "123", "comment-456", "Updated comment"
    )


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "--log-level", "DEBUG", "--log-format", "text", "test"])
def test_should_use_custom_log_settings(mock_app_class):
    mock_app = MagicMock()
    mock_app.config.provider = "github"
    mock_app.config.repo = "owner/repo"
    mock_app.config.base_url = None
    mock_app.client = MagicMock()
    mock_app.client.__class__.__name__ = "GitHubClient"
    mock_app_class.from_env.return_value = mock_app

    with patch("drift.__main__.setup_logging") as mock_setup_logging:
        with patch("sys.exit") as mock_exit:
            main()
            mock_exit.assert_not_called()

        mock_setup_logging.assert_called_once_with("DEBUG", "text")


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift"])
def test_should_print_help_when_no_command(mock_app_class, capsys):
    mock_app = MagicMock()
    mock_app_class.from_env.return_value = mock_app

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(1)

    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "Available commands" in captured.out


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "test"])
def test_should_handle_configuration_error(mock_app_class):
    from drift.exceptions import ConfigurationError

    mock_app_class.from_env.side_effect = ConfigurationError("Invalid config")

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(1)


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "analyze", "123"])
def test_should_handle_drift_exception(mock_app_class):
    from drift.exceptions import DriftException

    mock_app = MagicMock()
    mock_app_class.from_env.return_value = mock_app
    mock_app.analyze_pr.side_effect = DriftException("API error")

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(1)


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "test"])
def test_should_handle_keyboard_interrupt(mock_app_class):
    mock_app_class.from_env.side_effect = KeyboardInterrupt()

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(130)


@patch("drift.__main__.DriftApplication")
@patch("sys.argv", ["drift", "test"])
def test_should_handle_unexpected_error(mock_app_class):
    mock_app_class.from_env.side_effect = Exception("Unexpected error")

    with patch("sys.exit") as mock_exit:
        main()
        mock_exit.assert_called_once_with(1)
