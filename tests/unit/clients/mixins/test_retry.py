from unittest.mock import Mock, patch

import pytest

from drift.clients.mixins.retry import RetryMixin
from drift.exceptions import NetworkError, RateLimitError, TimeoutError


class TestRetryClass(RetryMixin):
    def __init__(self) -> None:
        super().__init__()


def test_should_succeed_on_first_attempt_when_function_works() -> None:
    instance = TestRetryClass()
    mock_func = Mock(return_value="success")

    wrapped = instance.with_retry(mock_func)
    result = wrapped()

    assert result == "success"
    assert mock_func.call_count == 1


def test_should_retry_and_succeed_when_function_eventually_works() -> None:
    instance = TestRetryClass()
    mock_func = Mock(side_effect=[NetworkError("fail"), "success"])

    wrapped = instance.with_retry(mock_func, max_retries=3, backoff_factor=0.01)

    with patch("time.sleep") as mock_sleep:
        result = wrapped()

    assert result == "success"
    assert mock_func.call_count == 2
    assert mock_sleep.call_count == 1


def test_should_raise_exception_when_all_retry_attempts_fail() -> None:
    instance = TestRetryClass()
    mock_func = Mock(side_effect=NetworkError("persistent failure"))
    mock_func.__name__ = "mock_func"

    wrapped = instance.with_retry(mock_func, max_retries=3, backoff_factor=0.01)

    with patch("time.sleep"):
        with pytest.raises(NetworkError, match="persistent failure"):
            wrapped()

    assert mock_func.call_count == 3


def test_should_use_exponential_backoff_when_jitter_is_disabled() -> None:
    instance = TestRetryClass()
    mock_func = Mock(
        side_effect=[TimeoutError("fail"), TimeoutError("fail"), "success"]
    )

    wrapped = instance.with_retry(
        mock_func,
        max_retries=3,
        backoff_factor=1.0,
        jitter=False,
    )

    sleep_times = []

    def mock_sleep(seconds: float) -> None:
        sleep_times.append(seconds)

    with patch("time.sleep", side_effect=mock_sleep):
        result = wrapped()

    assert result == "success"
    assert len(sleep_times) == 2
    assert sleep_times[0] > 0
    # With the fix, first retry uses exponent 0 (wait = 1.0 * 2^0 = 1.0)
    # second retry uses exponent 1 (wait = 1.0 * 2^1 = 2.0)
    assert sleep_times[0] == 1.0  # First retry: backoff_factor * 2^0
    assert sleep_times[1] == 2.0  # Second retry: backoff_factor * 2^1


def test_should_respect_max_wait_when_backoff_exceeds_limit() -> None:
    instance = TestRetryClass()
    mock_func = Mock(side_effect=[NetworkError("fail")] * 5 + ["success"])

    wrapped = instance.with_retry(
        mock_func,
        max_retries=6,
        backoff_factor=10.0,
        max_wait=5.0,
        jitter=False,
    )

    sleep_times = []

    def mock_sleep(seconds: float) -> None:
        sleep_times.append(seconds)

    with patch("time.sleep", side_effect=mock_sleep):
        result = wrapped()

    assert result == "success"
    assert all(t <= 5.0 for t in sleep_times)


def test_should_wait_reset_time_when_rate_limit_error_occurs() -> None:
    instance = TestRetryClass()
    mock_func = Mock(
        side_effect=[
            RateLimitError(3, "Rate limited"),
            "success",
        ]
    )

    wrapped = instance.with_retry(
        mock_func,
        max_retries=2,
        retry_on=(RateLimitError,),
    )

    sleep_times = []

    def mock_sleep(seconds: float) -> None:
        sleep_times.append(seconds)

    with patch("time.sleep", side_effect=mock_sleep):
        result = wrapped()

    assert result == "success"
    assert len(sleep_times) == 1
    assert sleep_times[0] == 3


def test_should_not_retry_when_error_is_not_retryable() -> None:
    instance = TestRetryClass()
    mock_func = Mock(side_effect=ValueError("not retryable"))
    mock_func.__name__ = "mock_func"

    wrapped = instance.with_retry(
        mock_func,
        max_retries=3,
        retry_on=(NetworkError, TimeoutError),
    )

    with pytest.raises(ValueError, match="not retryable"):
        wrapped()

    assert mock_func.call_count == 1


def test_should_handle_zero_retries_correctly() -> None:
    instance = TestRetryClass()
    mock_func = Mock(return_value="success")

    wrapped = instance.with_retry(mock_func, max_retries=0)
    result = wrapped()

    assert result == "success"
    assert mock_func.call_count == 1
