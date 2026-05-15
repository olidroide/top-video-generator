"""Unit tests for PublishVideoUseCase."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

import pytest

from src.application.fetch_top_videos_use_case import FetchTopVideosResult
from src.application.publish_video_use_case import (
    PublishVideoRequest,
    PublishVideoUseCase,
    WeeklyHorizontalPublishRequest,
    WeeklyHorizontalPublishUseCase,
)
from src.domain.models import CanonicalVideo, Channel, Platform, PublishingResult, Release, ReleaseKind, Video
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


def make_video(video_id: str, *, score: int | None = None) -> Video:
    return Video(
        video_id=video_id,
        views=1000,
        likes=100,
        score=score,
        title=f"Track {video_id}",
        description="#top #music",
        channel=Channel(name="Artist"),
    )


class _ReleaseStoreStub:
    def __init__(self, *, already_published: bool = False, persist_raises: bool = False) -> None:
        self.already_published = already_published
        self.persist_raises = persist_raises
        self.saved: list[Release] = []

    def is_release_at_date(self, platform: str, release_date: date, release_kind: str | None = None) -> bool:
        assert platform == Platform.YOUTUBE.value
        assert release_kind == ReleaseKind.WEEKLY_HORIZONTAL.value
        _ = release_date
        return self.already_published

    def add_or_update_release(self, release: Release) -> Release:
        if self.persist_raises:
            raise RuntimeError("persist failed")
        self.saved.append(release)
        return release


class TestWeeklyHorizontalPublishUseCase:
    @pytest.mark.asyncio
    async def test_returns_early_when_already_published(self) -> None:
        release_store = _ReleaseStoreStub(already_published=True)
        fetch_use_case = SimpleNamespace(execute=AsyncMock())
        pipeline = SimpleNamespace(build_horizontal_video=AsyncMock())
        uploader = SimpleNamespace(upload_weekly_video=AsyncMock())

        use_case = WeeklyHorizontalPublishUseCase(
            release_store=release_store,
            fetch_top_videos_use_case=fetch_use_case,
            horizontal_video_pipeline=pipeline,
            uploader=uploader,
        )

        result = await use_case.execute(
            WeeklyHorizontalPublishRequest(
                day=date(2026, 5, 15),
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@",
                yt_playlist_id_weekly="playlist-weekly",
                yt_auth_user_id="yt-owner",
            )
        )

        assert result.already_completed is True
        assert result.success is True
        fetch_use_case.execute.assert_not_awaited()
        pipeline.build_horizontal_video.assert_not_awaited()
        uploader.upload_weekly_video.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persists_release_after_successful_upload(self) -> None:
        release_store = _ReleaseStoreStub(already_published=False)
        fetch_use_case = SimpleNamespace(
            execute=AsyncMock(return_value=FetchTopVideosResult(videos=(make_video("v1", score=1),)))
        )
        pipeline = SimpleNamespace(build_horizontal_video=AsyncMock(return_value=("/tmp/final.mp4", "/tmp/thumb.png")))
        uploader = SimpleNamespace(upload_weekly_video=AsyncMock(return_value="yt_123"))

        use_case = WeeklyHorizontalPublishUseCase(
            release_store=release_store,
            fetch_top_videos_use_case=fetch_use_case,
            horizontal_video_pipeline=pipeline,
            uploader=uploader,
        )

        result = await use_case.execute(
            WeeklyHorizontalPublishRequest(
                day=date(2026, 5, 15),
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@",
                yt_playlist_id_weekly="playlist-weekly",
                yt_auth_user_id="yt-owner",
            )
        )

        assert result.success is True
        assert result.published_id == "yt_123"
        assert result.persisted_release is True
        assert len(release_store.saved) == 1
        assert release_store.saved[0].platform == Platform.YOUTUBE.value
        assert release_store.saved[0].client_id == "yt-owner"

    @pytest.mark.asyncio
    async def test_returns_error_when_upload_raises(self) -> None:
        release_store = _ReleaseStoreStub(already_published=False)
        fetch_use_case = SimpleNamespace(
            execute=AsyncMock(return_value=FetchTopVideosResult(videos=(make_video("v1", score=1),)))
        )
        pipeline = SimpleNamespace(build_horizontal_video=AsyncMock(return_value=("/tmp/final.mp4", "/tmp/thumb.png")))
        uploader = SimpleNamespace(upload_weekly_video=AsyncMock(side_effect=RuntimeError("upload failed")))

        use_case = WeeklyHorizontalPublishUseCase(
            release_store=release_store,
            fetch_top_videos_use_case=fetch_use_case,
            horizontal_video_pipeline=pipeline,
            uploader=uploader,
        )

        result = await use_case.execute(
            WeeklyHorizontalPublishRequest(
                day=date(2026, 5, 15),
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@",
                yt_playlist_id_weekly="playlist-weekly",
                yt_auth_user_id="yt-owner",
            )
        )

        assert result.success is False
        assert "upload failed" in (result.error or "")
        assert release_store.saved == []

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_fail_publish_result(self) -> None:
        release_store = _ReleaseStoreStub(already_published=False, persist_raises=True)
        fetch_use_case = SimpleNamespace(
            execute=AsyncMock(return_value=FetchTopVideosResult(videos=(make_video("v1", score=1),)))
        )
        pipeline = SimpleNamespace(build_horizontal_video=AsyncMock(return_value=("/tmp/final.mp4", "/tmp/thumb.png")))
        uploader = SimpleNamespace(upload_weekly_video=AsyncMock(return_value="yt_123"))

        use_case = WeeklyHorizontalPublishUseCase(
            release_store=release_store,
            fetch_top_videos_use_case=fetch_use_case,
            horizontal_video_pipeline=pipeline,
            uploader=uploader,
        )

        result = await use_case.execute(
            WeeklyHorizontalPublishRequest(
                day=date(2026, 5, 15),
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@",
                yt_playlist_id_weekly="playlist-weekly",
                yt_auth_user_id="yt-owner",
            )
        )

        assert result.success is True
        assert result.published_id == "yt_123"
        assert result.persisted_release is False
