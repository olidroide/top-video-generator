"""Unit tests for PublishVideoUseCase."""

from __future__ import annotations

from unittest.mock import AsyncMock, create_autospec

import pytest

from src.application.publish_video_use_case import (
    PublishVideoRequest,
    PublishVideoUseCase,
)
from src.domain.models import CanonicalVideo, Platform, PublishingResult
from src.domain.ports import VideoPublisher


def make_canonical_video(video_id: str = "v1") -> CanonicalVideo:
    return CanonicalVideo(
        video_id=video_id,
        title="Test Song",
        channel_name="Artist",
        views=1000,
    )


def make_request(videos: tuple[CanonicalVideo, ...] | None = None) -> PublishVideoRequest:
    return PublishVideoRequest(
        video_list=videos or (make_canonical_video(),),
        file_path="/tmp/video.mp4",
        title="Top 10",
        description="Description text",
    )


def make_publisher(platform: Platform = Platform.YOUTUBE, *, success: bool = True) -> VideoPublisher:
    mock = create_autospec(VideoPublisher, instance=True)
    mock.platform_name = platform
    mock.is_enabled = True
    mock.publish_video = AsyncMock(
        return_value=PublishingResult(
            platform=platform,
            success=success,
            published_id="pub_123" if success else None,
            error=None if success else "Upload failed",
        )
    )
    return mock


class TestPublishVideoUseCase:
    async def test_single_publisher_success(self) -> None:
        publisher = make_publisher()
        use_case = PublishVideoUseCase([publisher])
        request = make_request()

        result = await use_case.execute(request)

        assert result.all_succeeded
        assert len(result.results) == 1
        assert result.results[0].success
        assert result.results[0].platform == Platform.YOUTUBE

    async def test_multiple_publishers_all_success(self) -> None:
        publishers = [
            make_publisher(Platform.YOUTUBE),
            make_publisher(Platform.TIKTOK),
            make_publisher(Platform.INSTAGRAM),
        ]
        use_case = PublishVideoUseCase(publishers)

        result = await use_case.execute(make_request())

        assert result.all_succeeded
        assert len(result.results) == 3

    async def test_one_failure_does_not_abort_others(self) -> None:
        """A failing publisher must not prevent the others from running."""
        yt_publisher = make_publisher(Platform.YOUTUBE, success=True)
        failing_publisher = make_publisher(Platform.TIKTOK, success=False)
        use_case = PublishVideoUseCase([yt_publisher, failing_publisher])

        result = await use_case.execute(make_request())

        assert not result.all_succeeded
        assert len(result.results) == 2
        assert len(result.failed) == 1
        assert result.failed[0].platform == Platform.TIKTOK

    async def test_publisher_exception_is_caught(self) -> None:
        """Unexpected exception inside publish_video must be caught and recorded."""
        mock = create_autospec(VideoPublisher, instance=True)
        mock.platform_name = Platform.INSTAGRAM
        mock.is_enabled = True
        mock.publish_video = AsyncMock(side_effect=RuntimeError("unexpected crash"))
        use_case = PublishVideoUseCase([mock])

        result = await use_case.execute(make_request())

        assert not result.all_succeeded
        assert len(result.failed) == 1
        assert "unexpected crash" in (result.failed[0].error or "")

    async def test_empty_publishers_returns_empty_results(self) -> None:
        use_case = PublishVideoUseCase([])
        result = await use_case.execute(make_request())
        assert result.all_succeeded
        assert len(result.results) == 0

    async def test_publish_video_is_called_with_request_args(self) -> None:
        publisher = make_publisher()
        use_case = PublishVideoUseCase([publisher])
        request = make_request()

        await use_case.execute(request)

        publisher.publish_video.assert_awaited_once_with(
            video_list=request.video_list,
            file_path=request.file_path,
            title=request.title,
            description=request.description,
        )
