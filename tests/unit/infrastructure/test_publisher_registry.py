"""Unit tests for publisher registry."""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import MagicMock

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


def _all_enabled_reader() -> MagicMock:
    reader = MagicMock()
    reader.is_enabled.return_value = True
    return reader


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

    result = publisher_registry.build_publishers(_all_enabled_reader())

    assert [publisher.platform_name for publisher in result] == [Platform.YOUTUBE, Platform.TIKTOK]


def test_build_publishers_filters_by_admin_toggle(monkeypatch) -> None:
    from src.infrastructure import publisher_registry

    monkeypatch.setattr(
        publisher_registry,
        "InstagramPublisher",
        lambda: FakePublisher(Platform.INSTAGRAM, True),
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

    def _side_effect(platform: str) -> bool:
        return platform != "tiktok"

    reader = MagicMock()
    reader.is_enabled.side_effect = _side_effect

    result = publisher_registry.build_publishers(reader)

    assert {p.platform_name for p in result} == {Platform.YOUTUBE, Platform.INSTAGRAM}


def test_build_publishers_works_without_state_reader(monkeypatch) -> None:
    from src.infrastructure import publisher_registry

    monkeypatch.setattr(
        publisher_registry,
        "YouTubePublisher",
        lambda: FakePublisher(Platform.YOUTUBE, True),
    )
    monkeypatch.setattr(
        publisher_registry,
        "TikTokPublisher",
        lambda: FakePublisher(Platform.TIKTOK, True),
    )
    monkeypatch.setattr(
        publisher_registry,
        "InstagramPublisher",
        lambda: FakePublisher(Platform.INSTAGRAM, True),
    )

    result = publisher_registry.build_publishers()

    assert len(result) == 3


def test_build_publishers_filters_by_target_platforms(monkeypatch) -> None:
    from src.infrastructure import publisher_registry

    monkeypatch.setattr(
        publisher_registry,
        "InstagramPublisher",
        lambda: FakePublisher(Platform.INSTAGRAM, True),
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

    result = publisher_registry.build_publishers(
        _all_enabled_reader(),
        target_platforms={"instagram"},
    )

    assert [publisher.platform_name for publisher in result] == [Platform.INSTAGRAM]
