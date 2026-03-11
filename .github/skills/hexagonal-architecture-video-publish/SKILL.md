---
name: hexagonal-architecture-video-publish
description: "Hexagonal Architecture (Ports & Adapters) for the video publishing pipeline. Triggers on: VideoPublisher, VideoDataSource, CanonicalVideo, PublishingResult, publisher_registry, ports, adapters, domain, hexagonal, build_publishers, TaskGroup publish."
compatibility: "Project runtime declared in pyproject.toml. asyncio.TaskGroup. Pydantic v2. typing.Protocol with runtime_checkable."
---

# Hexagonal Architecture — Video Publish Pipeline

## Pattern 1: New Publisher Adapter

```python
# src/adapters/x_twitter_publisher.py
class XTwitterPublisher:
    @property
    def platform_name(self) -> Platform:
        return Platform.X_TWITTER

    @property
    def is_enabled(self) -> bool:
        return bool(get_app_settings().x_twitter_bearer_token)

    async def publish_video(
        self, video_list: list[CanonicalVideo], file_path: str,
        title: str, description: str,
    ) -> PublishingResult:
        try:
            post_id = await _upload_to_x(file_path, title)
            return PublishingResult(platform=self.platform_name, success=True,
                                    published_id=post_id, published_at=datetime.now(timezone.utc))
        except Exception as exc:
            logger.error("publish failed", error=str(exc))
            return PublishingResult(platform=self.platform_name, success=False,
                                    published_at=datetime.now(timezone.utc), error=str(exc))
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
async with asyncio.TaskGroup() as tg:
    for publisher in active_publishers:
        tg.create_task(publisher.publish_video(
            video_list=video_list, file_path=file_path,
            title=title, description=description,
        ))
```

## Pattern 4: MockPublisher for tests

```python
class MockPublisher:
    def __init__(self, platform: Platform, succeed: bool = True) -> None:
        self._platform = platform
        self._succeed = succeed
        self.calls: list[dict] = []

    @property
    def platform_name(self) -> Platform: return self._platform
    @property
    def is_enabled(self) -> bool: return True

    async def publish_video(self, video_list, file_path, title, description) -> PublishingResult:
        self.calls.append({"file_path": file_path, "title": title})
        return PublishingResult(
            platform=self._platform, success=self._succeed,
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
- `PublishingResult.success=False` is valid — adapters must never raise up to orchestrators.

## Quality Gates

- [ ] `ty check src/domain/` → zero errors.
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
> Return `PublishingResult` on both success and failure — never raise.
> Add protocol compliance coverage in `tests/unit/adapters/test_protocol_compliance.py`
> using `create_autospec`, not a module-level assertion.
> Register it in `src/infrastructure/publisher_registry.py`."
