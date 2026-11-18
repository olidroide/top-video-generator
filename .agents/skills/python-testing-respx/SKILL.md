---
name: python-testing-respx
description: "Mocking async HTTP requests in tests. Triggers on: respx, test api, mock http, httpx, integration test, adapter test, 429, 503."
---

# Testing HTTP Integrations

## Core Directives

- Use `respx` to intercept **outbound HTTP** in e2e/integration tests that drive the FastAPI app via `httpx.AsyncClient`.
- For **unit tests of adapters/use cases**, use `create_autospec` to mock the port interface — do not mock HTTP at transport level.
- Never mock `aiohttp.ClientSession` internals manually with `unittest.mock.patch`.
- `pytest-asyncio` is configured with `asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed.

## Pattern 1: E2E Test — FastAPI App + respx (outbound mocking)

`respx.mock` intercepts outbound HTTP calls made via `httpx` (which FastAPI's test machinery uses).

```python
import httpx
import pytest
import respx
from httpx import Response

from src.web.main import app


@respx.mock
async def test_trending_endpoint_returns_videos():
    # 1. Mock the outbound third-party call
    respx.get("https://www.googleapis.com/youtube/v3/videos").mock(
        return_value=Response(200, json={"items": [{"id": "xyz123", "snippet": {"title": "Test"}}]})
    )

    # 2. Drive the FastAPI app via httpx
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/trending")

    assert response.status_code == 200
```

## Pattern 2: Simulating Error Responses (Rate Limit, Outage)

Test that adapters and use cases handle 4xx/5xx from upstream APIs correctly.

```python
from src.domain.exceptions import PublishError


@respx.mock
async def test_adapter_handles_rate_limit():
    respx.post("https://open.tiktokapis.com/v2/post/publish/video/upload/").mock(
        return_value=Response(429, json={"error": {"code": "rate_limited"}})
    )

    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/api/publish", json={"video_id": "abc"})

    assert response.status_code in (429, 503)
```

## Pattern 3: Unit Tests — Mock the Port, Not HTTP

For unit tests of the application layer, always mock at the adapter/port boundary using `create_autospec`.

```python
from unittest.mock import AsyncMock, create_autospec

from src.application.publish_video_use_case import PublishVideoUseCase
from src.domain.exceptions import PublishError
from src.domain.ports import VideoPublisher


async def test_use_case_continues_on_single_platform_failure():
    mock_publisher = create_autospec(VideoPublisher, instance=True)
    mock_publisher.publish_video = AsyncMock(side_effect=PublishError("network error"))
    mock_publisher.platform_name = "tiktok"

    use_case = PublishVideoUseCase(publishers=[mock_publisher])
    results = await use_case.execute(request)

    assert results[0].success is False
    assert "network error" in results[0].error
```

## Anti-Patterns

| ❌ Anti-pattern | ✅ Correct |
|---|---|
| `unittest.mock.patch("aiohttp.ClientSession.get", ...)` | `create_autospec(VideoPublisher)` for unit, `respx.mock` for e2e |
| Making real API calls in tests | Intercept with `respx` or mock the port |
| Asserting on raw response dicts | Assert on canonical models (`CanonicalVideo`, `PublishingResult`) |
| `@pytest.mark.asyncio` on every test | Not needed — `asyncio_mode = "auto"` in `pyproject.toml` |
