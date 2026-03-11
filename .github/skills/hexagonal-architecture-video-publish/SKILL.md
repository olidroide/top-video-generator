---
name: hexagonal-architecture-video-publish
description: "Hexagonal Architecture (Ports & Adapters) for the video publishing pipeline. Triggers on: VideoPublisher, VideoDataSource, CanonicalVideo, PublishingResult, publisher_registry, ports, adapters, domain, hexagonal, build_publishers, TaskGroup publish."
compatibility: "Project runtime declared in pyproject.toml. asyncio.TaskGroup. Pydantic v2. typing.Protocol with runtime_checkable."
---

# Hexagonal Architecture — Video Publish Pipeline

## Pattern 1: New Publisher Adapter

```python
# src/adapters/x_twitter_publisher.py
from collections.abc import Sequence

from src.domain.exceptions import PublishError


class XTwitterPublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.X_TWITTER

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().x_twitter_bearer_token)

    async def publish_video(
        self,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult:
        try:
            post_id = await _upload_to_x(file_path, title)
            return PublishingResult(
                platform=self.platform_name,
                success=True,
                published_id=post_id,
                published_at=datetime.now(timezone.utc),
            )
        except (HTTPStatusError, TimeoutError) as exc:
            raise PublishError(platform=str(self.platform_name), cause=exc) from exc
```

## Pattern 2: Registry

```python
# src/infrastructure/publisher_registry.py
def build_publishers() -> list[VideoPublisher]:
    from src.adapters.instagram_publisher import InstagramPublisher
    from src.adapters.tiktok_publisher import TikTokPublisher
    from src.adapters.youtube_publisher import YouTubePublisher

    candidates: list[VideoPublisher] = [
        InstagramPublisher(), TikTokPublisher(), YouTubePublisher(),
    ]
    active = [p for p in candidates if p.is_enabled]
    logger.info("Publishers loaded", active=[p.platform_name for p in active])
    return active
```

## Pattern 3: Parallel Publish (TaskGroup)

```python
from collections.abc import Sequence

from src.domain.exceptions import PublishError


async def _publish_one(
    publisher: VideoPublisher,
    video_list: Sequence[CanonicalVideo],
    file_path: str,
    title: str,
    description: str,
) -> PublishingResult:
    try:
        return await publisher.publish_video(
            video_list=video_list,
            file_path=file_path,
            title=title,
            description=description,
        )
    except PublishError as exc:
        logger.warning("publish_failed", platform=publisher.platform_name, error=str(exc))
        return PublishingResult(
            platform=publisher.platform_name,
            success=False,
            error=str(exc),
        )


async with asyncio.TaskGroup() as tg:
    tasks = [
        tg.create_task(_publish_one(publisher, video_list, file_path, title, description))
        for publisher in active_publishers
    ]

results = [task.result() for task in tasks]
```

## Pattern 4: MockPublisher for tests

```python
from collections.abc import Sequence


class MockPublisher:
    def __init__(self, platform: Platform, succeed: bool = True) -> None:
        self._platform = platform
        self._succeed = succeed
        self.calls: list[dict[str, str]] = []

    @property
    def platform_name(self) -> Platform: return self._platform
    @property
    def is_enabled(self) -> bool: return True

    async def publish_video(
        self,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult:
        self.calls.append({"file_path": file_path, "title": title})
        return PublishingResult(
            platform=self._platform,
            success=self._succeed,
            published_id="mock-id-123" if self._succeed else None,
            published_at=datetime.now(timezone.utc),
            error=None if self._succeed else "mock error",
        )
```

## Non-Negotiable Rules

- `domain/` has zero imports from `src/` — only stdlib + pydantic.
- Adapters never import from other adapters.
- Scripts never reference `InstagramClient`, `TikTokClient`, `YTClient` directly.
- Protocol compliance belongs in tests, not in module-level assertions.
- `PublishingResult.success=False` is valid for expected platform failures.
- Map expected platform failures to `PublishingResult`; let programmer errors surface unless the use case explicitly wraps them.

## Quality Gates

- [ ] `uv run ruff format src/ tests/`
- [ ] `uv run ruff check src/ tests/`
- [ ] `uv run ty check src/`
- [ ] `uv run pytest`
- [ ] Protocol compliance covered in `tests/unit/adapters/test_protocol_compliance.py` with `create_autospec`.
- [ ] `build_publishers()` test: mock settings → verify enabled/disabled adapters.
- [ ] Parallel test: `MockPublisher(succeed=False)` on one platform → others complete.

## Protocol Compliance Test Pattern

```python
from unittest.mock import create_autospec

from src.domain.ports import VideoPublisher


def test_example_publisher_implements_protocol() -> None:
    from src.adapters.example_publisher import ExamplePublisher

    mock = create_autospec(ExamplePublisher, instance=True)
    assert isinstance(mock, VideoPublisher)
```

## Copilot Prompt Template

> "Create `src/adapters/{platform}_publisher.py` implementing the `VideoPublisher` protocol
> from `src/domain/ports.py`. Use `asyncio.to_thread` if the client is synchronous.
> Map expected platform failures to `PublishingResult` and avoid propagating those from concurrent publish orchestration.
> Add protocol compliance coverage in `tests/unit/adapters/test_protocol_compliance.py`
> using `create_autospec`, not a module-level assertion.
> Register it in `src/infrastructure/publisher_registry.py`."
