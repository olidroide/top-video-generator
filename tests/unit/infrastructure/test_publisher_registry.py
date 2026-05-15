"""Unit tests for publisher registry."""

from __future__ import annotations

from collections.abc import Sequence

from src.domain.models import CanonicalVideo, Platform, PublishingResult


class FakePublisher:
    def __init__(self, platform_name: Platform, is_enabled: bool) -> None:
        self._platform_name = platform_name
        self._is_enabled = is_enabled

    @property
    def platform_name(self) -> Platform:
        return self._platform_name

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    async def publish_video(
        self,
        video_list: Sequence[CanonicalVideo],
        file_path: str,
        title: str,
        description: str,
    ) -> PublishingResult:
        _ = video_list, file_path, title, description
        return PublishingResult(platform=self.platform_name, success=True)


def test_build_publishers_filters_disabled_publishers(monkeypatch) -> None:
    from src.infrastructure import publisher_registry

    monkeypatch.setattr(
        publisher_registry,
        "InstagramPublisher",
        lambda: FakePublisher(Platform.INSTAGRAM, False),
    )
    monkeypatch.setattr(
        publisher_registry,
        "TikTokPublisher",
        lambda: FakePublisher(Platform.TIKTOK, True),
    )
    monkeypatch.setattr(
        publisher_registry,
        "YouTubePublisher",
        lambda: FakePublisher(Platform.YOUTUBE, True),
    )

    result = publisher_registry.build_publishers()

    assert [publisher.platform_name for publisher in result] == [Platform.YOUTUBE, Platform.TIKTOK]
