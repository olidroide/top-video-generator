"""Unit tests for GetTopVideosDashboardUseCase."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, create_autospec

from src.application.fetch_top_videos_use_case import FetchTopVideosResult, FetchTopVideosUseCase
from src.application.get_top_videos_dashboard_use_case import (
    GetTopVideosDashboardRequest,
    GetTopVideosDashboardResult,
    GetTopVideosDashboardUseCase,
)
from src.domain.exceptions import ScoringError
from src.domain.models import Channel, TimeseriesRange, Video
from src.domain.ports import ReleaseReadPort


def _make_video() -> Video:
    return Video(
        video_id="video-1",
        title="A Sample Song",
        channel=Channel(name="Channel A"),
        score=1,
        score_previous=2,
        views=1234,
        likes=98,
    )


def _build_fetch_use_case(videos: tuple[Video, ...]) -> FetchTopVideosUseCase:
    mock_use_case = create_autospec(FetchTopVideosUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=FetchTopVideosResult(videos=videos))
    return mock_use_case


def _build_release_port(published: bool = False) -> ReleaseReadPort:
    mock_port = create_autospec(ReleaseReadPort, instance=True)
    mock_port.is_release_at_date.return_value = published
    return mock_port


class TestGetTopVideosDashboardUseCase:
    async def test_returns_videos_and_release_status(self) -> None:
        videos = (_make_video(),)
        use_case = GetTopVideosDashboardUseCase(_build_fetch_use_case(videos), _build_release_port(True))

        result = await use_case.execute(
            GetTopVideosDashboardRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result == GetTopVideosDashboardResult(videos=videos, yt_video_published=True)

    async def test_returns_empty_result_when_fetch_fails(self) -> None:
        mock_fetch = create_autospec(FetchTopVideosUseCase, instance=True)
        mock_fetch.execute = AsyncMock(
            side_effect=ScoringError("No video timeseries for today; run fetch script first")
        )
        use_case = GetTopVideosDashboardUseCase(mock_fetch, _build_release_port())

        result = await use_case.execute(
            GetTopVideosDashboardRequest(timeseries_range=TimeseriesRange.DAILY, day=date(2026, 3, 30))
        )

        assert result.videos == ()
        assert result.yt_video_published is False
        assert result.error_message is not None
