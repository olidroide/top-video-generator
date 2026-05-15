"""Retry utilities with exponential backoff and jitter."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from src.shared.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    jitter_range: tuple[float, float] = (0.0, 1.0)

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt with exponential backoff and jitter."""
        # Exponential backoff: base * (2 ^ attempt)
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add random jitter to prevent thundering herd
            jitter_amount = random.uniform(*self.jitter_range)  # noqa: S311
            delay += jitter_amount

        return delay


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""


def retry_with_backoff(
    config: RetryConfig | None = None, exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator for retrying async functions with exponential backoff.

    Args:
        config: Retry configuration. Uses defaults if not provided.
        exceptions: Tuple of exception types to catch and retry on.

    Example:
        @retry_with_backoff(
            config=RetryConfig(max_attempts=3, base_delay=2.0),
            exceptions=(ConnectionError, TimeoutError)
        )
        async def fetch_data():
            # Your async code here
            pass
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        func_name = getattr(func, "__name__", func.__class__.__name__)

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None

            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            "retry_with_backoff.attempt_failed",
                            attempt=attempt + 1,
                            max_attempts=config.max_attempts,
                            function=func_name,
                            delay_seconds=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.exception(
                            "retry_with_backoff.exhausted",
                            max_attempts=config.max_attempts,
                            function=func_name,
                            error=str(e),
                        )

            raise RetryExhaustedError(
                f"Function {func_name} failed after {config.max_attempts} attempts"
            ) from last_exception

        return wrapper

    return decorator


async def retry_async(  # noqa: UP047
    func: Callable[..., Awaitable[T]],
    *args: Any,
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """Execute an async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        config: Retry configuration
        exceptions: Exceptions to catch and retry on
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        RetryExhaustedError: If all attempts fail
    """
    if config is None:
        config = RetryConfig()

    last_exception: Exception | None = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = config.calculate_delay(attempt)
                logger.warning(
                    "retry_async.attempt_failed",
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay_seconds=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)
            else:
                logger.exception(
                    "retry_async.exhausted",
                    max_attempts=config.max_attempts,
                    error=str(e),
                )

    raise RetryExhaustedError(f"Function failed after {config.max_attempts} attempts") from last_exception
