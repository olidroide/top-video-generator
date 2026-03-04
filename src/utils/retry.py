"""Retry utilities with exponential backoff and jitter."""

import asyncio
import random
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

from src.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


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
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            # Add random jitter to prevent thundering herd
            jitter_amount = random.uniform(*self.jitter_range)
            delay += jitter_amount
        
        return delay


class RetryExhaustedError(Exception):
    """Raised when all retry attempts have been exhausted."""
    pass


def retry_with_backoff(
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
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
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < config.max_attempts - 1:
                        delay = config.calculate_delay(attempt)
                        logger.warning(
                            f"⚠️ Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"❌ All {config.max_attempts} attempts exhausted for {func.__name__}: {e}"
                        )
            
            raise RetryExhaustedError(
                f"Function {func.__name__} failed after {config.max_attempts} attempts"
            ) from last_exception
        
        return wrapper
    return decorator


async def retry_async(
    func: Callable[..., T],
    *args: Any,
    config: RetryConfig | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any
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
                    f"⚠️ Attempt {attempt + 1}/{config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"❌ All {config.max_attempts} attempts exhausted: {e}"
                )
    
    raise RetryExhaustedError(
        f"Function failed after {config.max_attempts} attempts"
    ) from last_exception
