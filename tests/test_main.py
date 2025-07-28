import logging

from drift.__main__ import main


def test_main_returns_zero():
    result = main()
    assert result == 0


def test_main_logs_message(caplog):
    with caplog.at_level(logging.INFO, logger="drift"):
        main()

    assert "Drift AI-powered architectural code review" in caplog.text
    assert "Starting analysis..." in caplog.text
