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
        """Test that execute is blocked when last fetch was earlier the same calendar day."""
        frozen_now = datetime(2026, 6, 2, 15, 0, 0, tzinfo=UTC)

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # pragma: no cover - deterministic helper
                return frozen_now if tz else frozen_now.replace(tzinfo=None)

        monkeypatch.setattr("src.application.fetch_data_use_case.datetime", _FrozenDateTime)

        # Same calendar day as frozen_now → should be blocked
        same_day_time = datetime(2026, 6, 2, 9, 0, 0, tzinfo=UTC)

        class _TimeseriesRepoStub:
            def __init__(self, _path: str) -> None:
                return

            def get_last_timestamp(self) -> datetime:
                return same_day_time

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

    def test_is_passed_enough_time_from_last_fetch_no_timestamp(self) -> None:
        """Test time check when no timestamp exists."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        use_case.timeseries_repo.get_last_timestamp.return_value = None

        result = use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True

    def test_is_passed_enough_time_from_last_fetch_sufficient_time(self) -> None:
        """Test time check when sufficient time has passed."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        past_time = datetime.now(UTC) - timedelta(days=2)
        use_case.timeseries_repo.get_last_timestamp.return_value = past_time

        result = use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True

    def test_is_passed_enough_time_from_last_fetch_insufficient_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test time check when last fetch was earlier the same calendar day."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        frozen_now = datetime(2026, 6, 2, 15, 0, 0, tzinfo=UTC)

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # pragma: no cover - deterministic helper
                return frozen_now if tz else frozen_now.replace(tzinfo=None)

        monkeypatch.setattr("src.application.fetch_data_use_case.datetime", _FrozenDateTime)

        # Same calendar day as frozen_now → not enough time
        use_case.timeseries_repo.get_last_timestamp.return_value = datetime(2026, 6, 2, 9, 0, 0, tzinfo=UTC)

        result = use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is False

    def test_is_passed_enough_time_from_last_fetch_boundary_23h59m53s(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Fetch is allowed when last run was the previous calendar day, even if
        fewer than 24 elapsed seconds have passed (e.g. 23h59m53s gap that spans
        midnight). The fix uses calendar-day comparison instead of strict seconds."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        frozen_now = datetime(2026, 6, 2, 13, 0, 0, tzinfo=UTC)

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # pragma: no cover - deterministic helper
                return frozen_now if tz else frozen_now.replace(tzinfo=None)

        monkeypatch.setattr("src.application.fetch_data_use_case.datetime", _FrozenDateTime)

        # Last fetch was 2026-06-01 (previous calendar day) → fetch must be allowed
        use_case.timeseries_repo.get_last_timestamp.return_value = frozen_now - timedelta(
            hours=23, minutes=59, seconds=53
        )

        result = use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True

    def test_is_passed_enough_time_from_last_fetch_boundary_exact_24h(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ensure exactly 24h elapsed allows fetch."""
        use_case = FetchDataUseCase(
            youtube_source=create_autospec(YouTubeSource),
            video_repo=create_autospec(VideoRepository),
            timeseries_repo=create_autospec(TimeSeriesRepository),
        )

        frozen_now = datetime(2026, 6, 2, 13, 0, 0, tzinfo=UTC)

        class _FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None) -> datetime:  # pragma: no cover - deterministic helper
                return frozen_now if tz else frozen_now.replace(tzinfo=None)

        monkeypatch.setattr("src.application.fetch_data_use_case.datetime", _FrozenDateTime)

        use_case.timeseries_repo.get_last_timestamp.return_value = frozen_now - timedelta(days=1)

        result = use_case._is_passed_enough_time_from_last_fetch(use_case.timeseries_repo, min_days=1)
        assert result is True
