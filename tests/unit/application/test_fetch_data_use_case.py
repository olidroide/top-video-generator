"""Unit tests for fetch_data_use_case module."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, create_autospec

import pytest

from src.adapters.youtube_source import YouTubeSource
from src.application.fetch_data_use_case import FetchDataUseCase
from src.config.settings import AppSettings
from src.domain.models import CanonicalVideo, VideoPoint
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository


@pytest.fixture
def mock_youtube_source() -> YouTubeSource:
    return create_autospec(YouTubeSource, instance=True)


@pytest.fixture
def mock_video_repo() -> VideoRepository:
    return create_autospec(VideoRepository, instance=True)


@pytest.fixture
def mock_timeseries_repo() -> TimeSeriesRepository:
    return create_autospec(TimeSeriesRepository, instance=True)


@pytest.fixture
def mock_settings() -> AppSettings:
    settings = create_autospec(AppSettings, instance=True)
    settings.db_data_file = "test_db.json"
    settings.db_video_file = "test_video_db.json"
    settings.db_timeseries_file = "test_ts.csv"
    settings.yt_search_region_code = "IN"
    settings.scheduler_lock_file = "/tmp/test.lock"
    return settings


@pytest.fixture
def fetch_data_use_case(
    mock_youtube_source: YouTubeSource,
    mock_video_repo: VideoRepository,
    mock_timeseries_repo: TimeSeriesRepository,
    mock_settings: AppSettings,
) -> FetchDataUseCase:
    return FetchDataUseCase(
        youtube_source=mock_youtube_source,
        video_repo=mock_video_repo,
        timeseries_repo=mock_timeseries_repo,
        settings=mock_settings,
    )


class TestFetchDataUseCase:
    """Tests for FetchDataUseCase."""

    @pytest.mark.asyncio
    async def test_execute_returns_video_points(
        self,
        fetch_data_use_case: FetchDataUseCase,
        mock_youtube_source: YouTubeSource,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that execute returns video points and calls dependencies correctly."""
        points_added: list[VideoPoint] = []

        class _TimeseriesRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def get_last_timestamp(self) -> None:
                return None

            def get_video_points_by_date_range(self, _from_dt: datetime, _until_dt: datetime) -> list:
                return []

            def add_video_point(self, video_point: VideoPoint) -> None:
                points_added.append(video_point)

        class _VideoRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def upsert(self, _video: CanonicalVideo) -> None:
                return

        canonical = CanonicalVideo(
            video_id="test123",
            title="Test Video",
            channel_name="Test Channel",
            views=1000,
            likes=50,
            description="Test Description",
            duration_seconds=180,
        )

        mock_youtube_source.fetch_trending_videos = AsyncMock(return_value=[SimpleNamespace(video_id="test123")])
        mock_youtube_source.fetch_video_details_batch = AsyncMock(return_value=[canonical])

        monkeypatch.setattr("src.application.fetch_data_use_case.TimeSeriesRepository", _TimeseriesRepoStub)
        monkeypatch.setattr("src.application.fetch_data_use_case.VideoRepository", _VideoRepoStub)

        # Execute
        result = await fetch_data_use_case.execute()

        # Assertions
        assert isinstance(result, list)
        mock_youtube_source.fetch_trending_videos.assert_called_once()
        mock_youtube_source.fetch_video_details_batch.assert_called_once()
        assert points_added
        assert all(point.score is not None and point.score >= 1 for point in points_added)
        assert all(point.views_growth is not None and point.views_growth > 0 for point in points_added)
        assert all(point.score is not None and point.score >= 1 for point in result)
        assert all(point.views_growth is not None and point.views_growth > 0 for point in result)

    @pytest.mark.asyncio
    async def test_execute_respects_time_window(
        self,
        fetch_data_use_case: FetchDataUseCase,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that execute respects minimum time window."""
        recent_time = datetime.now(UTC) - timedelta(hours=12)

        class _TimeseriesRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def get_last_timestamp(self) -> datetime:
                return recent_time

            def get_video_points_by_date_range(self, _from_dt: datetime, _until_dt: datetime) -> list:
                return []

            def add_video_point(self, _video_point: object) -> None:
                return

        class _VideoRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def upsert(self, _video: CanonicalVideo) -> None:
                return

        fetch_data_use_case.youtube_source.fetch_trending_videos = AsyncMock()

        monkeypatch.setattr("src.application.fetch_data_use_case.TimeSeriesRepository", _TimeseriesRepoStub)
        monkeypatch.setattr("src.application.fetch_data_use_case.VideoRepository", _VideoRepoStub)

        # Execute
        result = await fetch_data_use_case.execute()

        # Should return early without calling YouTube
        assert result == []
        fetch_data_use_case.youtube_source.fetch_trending_videos.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_force_fetch_bypasses_time_window(
        self,
        mock_youtube_source: YouTubeSource,
        mock_video_repo: VideoRepository,
        mock_timeseries_repo: TimeSeriesRepository,
        mock_settings: AppSettings,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        recent_time = datetime.now(UTC) - timedelta(hours=1)
        points_added: list[VideoPoint] = []

        class _TimeseriesRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def get_last_timestamp(self) -> datetime:
                return recent_time

            def get_video_points_by_date_range(self, _from_dt: datetime, _until_dt: datetime) -> list:
                return []

            def add_video_point(self, video_point: VideoPoint) -> None:
                points_added.append(video_point)

        class _VideoRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def upsert(self, _video: CanonicalVideo) -> None:
                return

        canonical = CanonicalVideo(
            video_id="forced123",
            title="Forced Video",
            channel_name="Channel",
            views=100,
            likes=10,
            description="desc",
            duration_seconds=60,
        )

        mock_youtube_source.fetch_trending_videos = AsyncMock(return_value=[SimpleNamespace(video_id="forced123")])
        mock_youtube_source.fetch_video_details_batch = AsyncMock(return_value=[canonical])

        monkeypatch.setattr("src.application.fetch_data_use_case.TimeSeriesRepository", _TimeseriesRepoStub)
        monkeypatch.setattr("src.application.fetch_data_use_case.VideoRepository", _VideoRepoStub)

        use_case = FetchDataUseCase(
            youtube_source=mock_youtube_source,
            video_repo=mock_video_repo,
            timeseries_repo=mock_timeseries_repo,
            settings=mock_settings,
            force_fetch=True,
        )

        result = await use_case.execute()

        assert len(result) == 1
        mock_youtube_source.fetch_trending_videos.assert_awaited_once()
        assert points_added
        assert result[0].score == 1
        assert result[0].views_growth == canonical.views
        assert points_added[0].score == 1
        assert points_added[0].views_growth == canonical.views

    @pytest.mark.asyncio
    async def test_is_passed_enough_time_from_last_fetch_no_timestamp(self) -> None:
        """Test time check when no timestamp exists."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        use_case.timeseries_repo.get_last_timestamp.return_value = None

        result = await use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_passed_enough_time_from_last_fetch_sufficient_time(self) -> None:
        """Test time check when sufficient time has passed."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        past_time = datetime.now(UTC) - timedelta(days=2)
        use_case.timeseries_repo.get_last_timestamp.return_value = past_time

        result = await use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True

    @pytest.mark.asyncio
    async def test_is_passed_enough_time_from_last_fetch_insufficient_time(self) -> None:
        """Test time check when insufficient time has passed."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        recent_time = datetime.now(UTC) - timedelta(hours=12)
        use_case.timeseries_repo.get_last_timestamp.return_value = recent_time

        result = await use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is False
