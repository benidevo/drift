from collections.abc import Callable
from typing import Any

from tenacity import (
    RetryCallState,
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
)

from drift.exceptions import NetworkError, RateLimitError, TimeoutError
from drift.logger import get_logger


class RetryMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._retry_logger = get_logger(f"{self.__class__.__name__}.RetryMixin")

    def with_retry(
        self,
        func: Callable[..., Any],
        max_retries: int = 3,
        backoff_factor: float = 1.0,
        max_wait: float = 60.0,
        jitter: bool = True,
        retry_on: tuple[type[Exception], ...] = (
            NetworkError,
            TimeoutError,
            ConnectionError,
        ),
    ) -> Callable[..., Any]:
        # Validate and cap max_retries to prevent retry storms
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")

        # Cap at reasonable maximum to prevent retry storms
        MAX_ALLOWED_RETRIES = 10
        effective_max_retries = min(max_retries, MAX_ALLOWED_RETRIES)
        if max_retries > MAX_ALLOWED_RETRIES:
            self._retry_logger.warning(
                f"max_retries capped at {MAX_ALLOWED_RETRIES} (was {max_retries})"
            )

        def wait_strategy(retry_state: RetryCallState) -> float:
            if retry_state.outcome and retry_state.outcome.failed:
                exception = retry_state.outcome.exception()

                if isinstance(exception, RateLimitError) and exception.reset_time:
                    wait_time = min(exception.reset_time, max_wait)
                    self._retry_logger.warning(
                        f"Rate limit hit. Waiting {wait_time}s until reset."
                    )
                    return wait_time

            retry_count = retry_state.attempt_number - 1

            if jitter:
                wait_func = wait_exponential_jitter(
                    initial=backoff_factor,
                    max=max_wait,
                    jitter=max_wait,
                )
                return wait_func(retry_state)
            else:
                exponent = max(retry_count, 0)
                wait_time = min(backoff_factor * (2**exponent), max_wait)
                return float(wait_time)

        def should_retry(retry_state: RetryCallState) -> bool:
            if not retry_state.outcome or not retry_state.outcome.failed:
                return False

            exception = retry_state.outcome.exception()

            if not isinstance(exception, retry_on):
                self._retry_logger.error(
                    f"Non-retryable error in {func.__name__}: {exception}"
                )
                return False

            if not isinstance(exception, RateLimitError):
                attempt = retry_state.attempt_number
                self._retry_logger.warning(
                    f"Attempt {attempt}/{effective_max_retries} failed: "
                    f"{exception}. Retrying..."
                )

            return True

        retry_decorator = retry(
            stop=stop_after_attempt(max(effective_max_retries, 1)),
            wait=wait_strategy,
            retry=should_retry,
            reraise=True,
        )

        return retry_decorator(func)
