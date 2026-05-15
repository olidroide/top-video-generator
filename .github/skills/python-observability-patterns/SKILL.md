---
name: python-observability-patterns
description: "Structured logging with structlog. Triggers on: log, logger, exception, structlog, observe, print, logging."
---

# Observability & Logging Patterns

## Core Directives

- **Import**: `from src.shared.logging import get_logger`—it wraps `structlog.get_logger()`.
- **Never** use `logging.getLogger()`, `logging.basicConfig()`, or bare `print()`.
- **Never** use f-strings or string concatenation in log calls. Pass all context as keyword arguments.

## Pattern 1: Canonical Logger Setup

```python
from src.shared.logging import get_logger

logger = get_logger(__name__)
```

## Pattern 2: Structured Event Logging

The first positional argument is the event name (dot-separated or underscore). All context goes as keyword arguments — structlog binds them as key-value pairs.

```python
# ❌ BAD
logger.info(f"Published video {video.id} to {platform}")

# ✅ GOOD
logger.info("video.published", video_id=video.id, platform=platform.value, duration_s=14.5)
logger.warning("publish.skipped", reason="already_published_today", platform=platform.value)
```

## Pattern 3: Exception Logging

Add `exc_info=True` to include the stack trace. Do not embed `str(exc)` as the event name.

```python
try:
    await publisher.publish(video)
except PublishError as exc:
    logger.error(
        "publish.failed",
        platform=publisher.platform_name,
        error=str(exc),
        exc_info=True,
    )
```

## Anti-Patterns

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `logging.getLogger("app")` | `get_logger(__name__)` |
| `logger.info(f"Processing {id}")` | `logger.info("processing", id=id)` |
| `print("Done")` | `logger.info("done")` |
| `logger.error("msg", extra={"key": val})` | `logger.error("msg", key=val)` |
| `logger.error(str(exc))` | `logger.error("task.failed", error=str(exc), exc_info=True)` |
