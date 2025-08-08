import pytest

from drift.exceptions import (
    APIError,
    AuthenticationError,
    ConfigurationError,
    DriftException,
    NetworkError,
    RateLimitError,
    ResourceNotFoundError,
    TimeoutError,
    ValidationError,
)


def test_should_include_reset_time_when_rate_limit_error_has_reset_time() -> None:
    reset_time = 1234567890
    with pytest.raises(RateLimitError) as exc_info:
        raise RateLimitError(reset_time, "Rate limit exceeded")

    error = exc_info.value
    assert "Rate limit exceeded" in str(error)
    assert error.reset_time == reset_time


def test_should_handle_none_when_rate_limit_error_has_no_reset_time() -> None:
    with pytest.raises(RateLimitError) as exc_info:
        raise RateLimitError(None, "Rate limit hit")

    error = exc_info.value
    assert error.reset_time is None
    assert "Rate limit hit" in str(error)


def test_should_include_status_code_when_api_error_has_status() -> None:
    with pytest.raises(APIError) as exc_info:
        raise APIError(status_code=500, message="Internal server error")

    error = exc_info.value
    assert error.status_code == 500
    assert error.message == "Internal server error"
    assert "Internal server error" in str(error)


def test_should_handle_none_when_api_error_has_no_status_code() -> None:
    with pytest.raises(APIError) as exc_info:
        raise APIError(message="Generic API error")

    error = exc_info.value
    assert error.status_code is None
    assert error.message == "Generic API error"


def test_should_inherit_from_drift_exception_when_using_custom_exceptions() -> None:
    exception_classes = [
        AuthenticationError,
        RateLimitError,
        ResourceNotFoundError,
        APIError,
        ConfigurationError,
        ValidationError,
        NetworkError,
        TimeoutError,
    ]

    for exc_class in exception_classes:
        instance = exc_class("test")
        assert isinstance(instance, DriftException)
        assert isinstance(instance, Exception)
