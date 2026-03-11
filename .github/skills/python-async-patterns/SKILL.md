---
name: python-async-patterns
description: "Python asyncio patterns. Triggers on: asyncio, TaskGroup, gather, await, concurrent, blocking I/O, to_thread, parallel execution."
compatibility: "Python 3.12+. TaskGroup and modern timeouts required."
---

# Python Async Patterns

## Core Directives

- **Use `asyncio.TaskGroup`** instead of `asyncio.gather` for structural concurrency.
- **Never block the event loop** with synchronous I/O or CPU-heavy work. Use `asyncio.to_thread`.
- Always handle exceptions explicitly per-task if you don't want a single failure to cancel the entire `TaskGroup`.

## Pattern 1: Concurrent Execution with TaskGroup

Unlike `gather`, `TaskGroup` does not return results from the `async with` block. Store task references before the context exits and call `.result()` after.

```python
import asyncio
from typing import Any

async def process_all(items: list[str]) -> list[Any]:
    tasks: list[asyncio.Task[Any]] = []

    async with asyncio.TaskGroup() as tg:
        for item in items:
            tasks.append(tg.create_task(process_one(item)))

    # Safe to read .result() — TaskGroup has exited successfully
    return [task.result() for task in tasks]
```

## Pattern 2: Fault-Tolerant TaskGroup

By default, if one task raises an unhandled exception, `TaskGroup` cancels all remaining tasks. To isolate per-task failures, catch exceptions *inside* the worker coroutine.

```python
async def _safe_process(item: str) -> Result | Exception:
    try:
        return await process_one(item)
    except Exception as exc:
        return exc  # Return error as value instead of propagating

async def process_independently(items: list[str]) -> list[Result | Exception]:
    tasks: list[asyncio.Task[Result | Exception]] = []
    async with asyncio.TaskGroup() as tg:
        for item in items:
            tasks.append(tg.create_task(_safe_process(item)))

    return [t.result() for t in tasks]
```

This is the same isolation strategy used in `_publish_one` for the video publishing pipeline — see `hexagonal-architecture-video-publish` skill.

## Pattern 3: Running Blocking Code (to_thread)

Offload synchronous blocking calls (legacy clients, Pillow, disk I/O) to a thread with `asyncio.to_thread`. This is the modern replacement for `loop.run_in_executor`.

```python
import asyncio

def blocking_transcode(path: str) -> str:
    # CPU/disk-heavy — must not run on the event loop directly
    ...

async def transcode_async(path: str) -> str:
    return await asyncio.to_thread(blocking_transcode, path)
```

Pass arguments positionally — `asyncio.to_thread` accepts `(func, *args, **kwargs)`.

## Pattern 4: Modern Timeouts

```python
import asyncio

async def fetch_with_timeout() -> str | None:
    try:
        async with asyncio.timeout(5.0):
            return await slow_network_call()
    except TimeoutError:
        return None
```

Use the built-in `TimeoutError` (not `asyncio.TimeoutError`) — they are the same in Python 3.11+. Do not use `asyncio.wait_for` for new code.

## Pattern 5: Bounded Concurrency

Use a `Semaphore` inside a `TaskGroup` when hitting rate-limited APIs.

```python
async def bounded_fetch(urls: list[str], limit: int = 5) -> list[str]:
    semaphore = asyncio.Semaphore(limit)

    async def _fetch(url: str) -> str:
        async with semaphore:
            return await fetch_one(url)

    tasks: list[asyncio.Task[str]] = []
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            tasks.append(tg.create_task(_fetch(url)))

    return [t.result() for t in tasks]
```

## Anti-Patterns to Correct

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `await asyncio.gather(*tasks)` | `async with asyncio.TaskGroup() as tg:` |
| `time.sleep(n)` inside async | `await asyncio.sleep(n)` |
| `requests.get(url)` inside async | `async with aiohttp.ClientSession()` |
| `loop.run_in_executor(None, fn)` | `await asyncio.to_thread(fn)` |
| `asyncio.create_task(work())` (orphaned) | Keep reference or use `TaskGroup` |
| No per-task error handling in TaskGroup | Wrap worker in `try/except` returning value |

## Async Context Manager

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_connection():
    conn = await create_connection()
    try:
        yield conn
    finally:
        await conn.close()
```

## See Also

- `hexagonal-architecture-video-publish` — `_publish_one` fault-tolerant TaskGroup pattern
- `python-fastapi-patterns` — async route handlers
- `video-processing-migration` — offloading blocking media ops with `to_thread`
