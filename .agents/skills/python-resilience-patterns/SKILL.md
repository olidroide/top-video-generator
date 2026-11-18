---
name: python-resilience-patterns
description: "Async resilience, retries, and HTTP client patterns. Triggers on: retry, timeout, HTTP request, rate limit, aiohttp, ClientSession, backoff."
---

# Python Resilience Patterns

## Core Directives

- **Never** write manual `while` retry loops with `asyncio.sleep()`.
- Use `src.utils.retry.retry_with_backoff` + `RetryConfig` — the canonical retry utility in this project.
- Use `aiohttp.ClientSession` as an async context manager. Never leave sessions unclosed.
- Always set `aiohttp.ClientTimeout` explicitly — no bare `session.get(url)` without a timeout.

## Pattern 1: Retry Decorator (Canonical)

```python
import aiohttp

from src.utils.retry import RetryConfig, retry_with_backoff

@retry_with_backoff(
    config=RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
    exceptions=(aiohttp.ClientError, TimeoutError),
)
async def fetch_platform_data(url: str) -> dict:
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=10.0)
    ) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.json()
```

`RetryConfig` defaults: `max_attempts=3`, `base_delay=1.0`, `max_delay=60.0`, `jitter=True`.

## Pattern 2: aiohttp Session — Multiple Requests

Share one session per use case / adapter call, not one per request.

```python
async with aiohttp.ClientSession(
    timeout=aiohttp.ClientTimeout(total=30.0)
) as session:
    data = await fetch_platform_data(session, url)
    details = await fetch_video_details(session, video_id)
```

## Pattern 3: Function Call Style (No Decorator)

`retry_async` is available for ad-hoc retries without decoration.

```python
from src.utils.retry import RetryConfig, retry_async

result = await retry_async(
    some_async_func,
    arg1,
    arg2,
    config=RetryConfig(max_attempts=5, base_delay=1.0),
    exceptions=(aiohttp.ClientError,),
)
```

## Anti-Patterns

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `while retries > 0: await asyncio.sleep(5)` | `@retry_with_backoff(config=RetryConfig(...))` |
| `aiohttp.ClientSession()` outside context manager | `async with aiohttp.ClientSession() as session:` |
| `session.get(url)` without timeout | `aiohttp.ClientTimeout(total=10.0)` on session |
| Importing tenacity directly | Use `src.utils.retry` — the project's canonical utility |
