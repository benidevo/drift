from collections.abc import Callable
from functools import wraps
import secrets
from time import sleep
from typing import Any

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
        """
        Decorator to retry a function with exponential backoff.

        Args:
            func: Function to retry
            max_retries: Maximum number of retry attempts
            backoff_factor: Base wait time multiplier
            max_wait: Maximum wait time between retries
            jitter: Add random jitter to wait time
            retry_on: Tuple of exception types to retry on
        """

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e

                    if isinstance(e, RateLimitError) and e.reset_time:
                        wait_time = min(e.reset_time, max_wait)
                        self._retry_logger.warning(
                            f"Rate limit hit. Waiting {wait_time}s until reset."
                        )
                    else:
                        wait_time = min(backoff_factor * (2**attempt), max_wait)

                        if jitter:
                            wait_time = wait_time * (
                                0.5 + secrets.SystemRandom().random()
                            )

                        self._retry_logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {wait_time:.2f}s..."
                        )

                    if attempt < max_retries - 1:
                        sleep(wait_time)
                except Exception as e:
                    self._retry_logger.error(
                        f"Non-retryable error in {func.__name__}: {e}"
                    )
                    raise

            if last_exception:
                self._retry_logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__}"
                )
                raise last_exception

            raise RuntimeError(f"Retry failed for {func.__name__} with no exception")

        return wrapper
