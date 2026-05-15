"""Unit tests for FetchTopVideosUseCase."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from src.application.fetch_top_videos_use_case import (
    FetchTopVideosRequest,
    FetchTopVideosUseCase,
)
from src.domain.exceptions import ScoringError
from src.domain.models import CanonicalVideo, Channel, TimeseriesRange, VideoPoint, VideoScoreStatus
from src.domain.ports import TimeSeriesReader, VideoMetadataReader

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_video_point(
    video_id: str,
    views: int = 1000,
    views_growth: int | None = None,
    score: int | None = None,
    score_status: VideoScoreStatus | None = None,
    title: str | None = None,
    description: str | None = None,
    channel: Channel | None = None,
    duration: int | None = None,
    dt: datetime | None = None,
) -> VideoPoint:
    return VideoPoint(
        time=dt or datetime(2026, 3, 31, 12, 0, 0, tzinfo=UTC),
        video_id=video_id,
        views=views,
        likes=0,
        views_growth=views_growth,
        score=score,
        score_status=score_status,
        title=title,
        description=description,
        channel=channel,
        duration=duration,
    )


def make_canonical_video(
    video_id: str,
    title: str = "Test Song",
    channel_name: str = "Test Channel",
    views: int = 1000,
    description: str = "Test Description",
    duration_seconds: float = 180.0,
) -> CanonicalVideo:
    return CanonicalVideo(
        video_id=video_id,
        title=title,
        channel_name=channel_name,
        views=views,
        description=description,
        duration_seconds=duration_seconds,
    )


def make_repo(
    current_points: list[VideoPoint],
    previous_points: list[VideoPoint] | None = None,
) -> TimeSeriesReader:
    """
    Returns a mock TimeSeriesReader that returns current_points for the main query
    and previous_points (or []) for the baseline.
    """
    mock = MagicMock(spec=TimeSeriesReader)
    call_count: list[int] = [0]

    def side_effect(start_time: datetime, end_time: datetime) -> list[VideoPoint]:
        call_count[0] += 1
        # First call = previous period (baseline); second = current period
        if call_count[0] == 1:
            return previous_points if previous_points is not None else []
        return current_points

    mock.get_video_points_by_date_range.side_effect = side_effect
    return mock


def make_video_repo(videos: list[CanonicalVideo] | None = None) -> VideoMetadataReader:
    mock = MagicMock(spec=VideoMetadataReader)
    by_video_id = {video.video_id: video for video in videos or []}
    mock.get.side_effect = lambda video_id: by_video_id.get(video_id)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFetchTopVideosUseCase:
    async def test_returns_ranked_videos_from_current_period(self) -> None:
        current = [make_video_point("v1", views=5000), make_video_point("v2", views=3000)]
        repo = make_repo(current)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.video_count == 2
        video_ids = {v.video_id for v in result.videos}
        assert video_ids == {"v1", "v2"}

    async def test_raises_scoring_error_when_no_current_data(self) -> None:
        repo = make_repo(current_points=[], previous_points=[])
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        with pytest.raises(ScoringError, match="No video timeseries for today"):
            await use_case.execute(FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30)))

    async def test_limit_is_respected(self) -> None:
        current = [make_video_point(f"v{i}", views=i * 100) for i in range(20)]
        repo = make_repo(current)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30), limit=5)
        )

        assert result.video_count == 5

    async def test_videos_sorted_by_growth_descending(self) -> None:
        previous = [
            make_video_point("v1", views=1000),
            make_video_point("v2", views=500),
        ]
        current = [
            make_video_point("v1", views=1200),  # growth 200
            make_video_point("v2", views=1500),  # growth 1000
        ]
        repo = make_repo(current, previous)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=date(2026, 3, 30))
        )

        assert result.videos[0].video_id == "v2"
        assert result.videos[1].video_id == "v1"

    async def test_new_video_gets_its_views_as_growth(self) -> None:
        """A video with no previous entry should use its raw views as growth."""
        current = [make_video_point("new_vid", views=800)]
        repo = make_repo(current, previous_points=[])
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.video_count == 1
        assert result.videos[0].video_id == "new_vid"

    async def test_existing_video_keeps_previous_rank_as_integer(self) -> None:
        previous = [make_video_point("v1", views=1000, score=4)]
        current = [make_video_point("v1", views=3200)]
        repo = make_repo(current, previous)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=date(2026, 3, 30))
        )

        assert result.videos[0].score == 1
        assert result.videos[0].score_previous == 4
        assert result.videos[0].score_status == VideoScoreStatus.UP

    async def test_default_limit_is_25(self) -> None:
        current = [make_video_point(f"v{i}", views=i * 10) for i in range(30)]
        repo = make_repo(current)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.video_count == 25

    async def test_timeseries_repo_called_twice(self) -> None:
        """Each execute() should query the repo twice: previous + current."""
        current = [make_video_point("v1")]
        repo = make_repo(current)
        use_case = FetchTopVideosUseCase(repo, make_video_repo())

        await use_case.execute(FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=date(2026, 3, 30)))

        assert repo.get_video_points_by_date_range.call_count == 2

    async def test_hydrates_video_metadata_from_repository(self) -> None:
        current = [make_video_point("v1", views=5000)]
        repo = make_repo(current)
        video_repo = make_video_repo(
            [
                make_canonical_video(
                    "v1",
                    title="Hydrated Song",
                    channel_name="Hydrated Channel",
                    views=5000,
                    description="Hydrated Description",
                    duration_seconds=182.0,
                )
            ]
        )
        use_case = FetchTopVideosUseCase(repo, video_repo)

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.video_count == 1
        video = result.videos[0]
        assert video.title == "Hydrated Song"
        assert video.description == "Hydrated Description"
        assert video.channel is not None
        assert video.channel.name == "Hydrated Channel"
        assert video.duration == 182

    async def test_keeps_existing_metadata_when_repository_is_missing_video(self) -> None:
        current = [
            make_video_point(
                "v1",
                views=5000,
                title="Existing Title",
                description="Existing Description",
                channel=Channel(name="Existing Channel"),
                duration=123,
            )
        ]
        repo = make_repo(current)
        use_case = FetchTopVideosUseCase(repo, make_video_repo([]))

        result = await use_case.execute(
            FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.video_count == 1
        video = result.videos[0]
        assert video.title == "Existing Title"
        assert video.description == "Existing Description"
        assert video.channel is not None
        assert video.channel.name == "Existing Channel"
        assert video.duration == 123
