"""Retry logic with exponential backoff and idempotency."""

import time
from typing import Any, Callable, Optional

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class NetworkTimeoutError(Exception):
    """Raised when network timeout occurs."""

    pass


class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""

    pass


class RetryHandler:
    """Handles retry logic with exponential backoff."""

    def __init__(self, max_attempts: int = 5, base_delay: int = 1):
        self.max_attempts = max_attempts
        self.base_delay = base_delay

    def execute_with_retry(
        self, func: Callable, *args, idempotency_key: Optional[str] = None, **kwargs
    ) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            idempotency_key: Key for idempotent operations
            *args, **kwargs: Arguments to pass to func

        Returns:
            Result from function execution
        """
        # Add idempotency key to kwargs if provided
        if idempotency_key:
            kwargs["idempotency_key"] = idempotency_key

        # Create retry decorator
        retry_decorator = retry(
            stop=stop_after_attempt(self.max_attempts),
            wait=wait_exponential(
                multiplier=self.base_delay, min=self.base_delay, max=10
            ),
            retry=retry_if_exception_type((NetworkTimeoutError, RateLimitError)),
        )

        # Apply retry decorator and execute
        retried_func = retry_decorator(func)
        return retried_func(*args, **kwargs)

    def should_retry(self, error: Exception) -> bool:
        """Determine if an error should trigger a retry."""
        retriable_errors = (NetworkTimeoutError, RateLimitError)
        return isinstance(error, retriable_errors)

    def calculate_backoff_delay(self, attempt: int) -> float:
        """Calculate exponential backoff delay for given attempt number."""
        return min(self.base_delay * (2**attempt), 10)
