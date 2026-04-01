"""Unit tests for FetchTrendingUseCase."""

from __future__ import annotations

from unittest.mock import AsyncMock, create_autospec

from src.application.fetch_trending_use_case import (
    FetchTrendingRequest,
    FetchTrendingUseCase,
)
from src.domain.models import CanonicalVideo
from src.domain.ports import TrendingVideoFetcher


def make_video(video_id: str, score: float = 0.0) -> CanonicalVideo:
    return CanonicalVideo(
        video_id=video_id,
        title=f"Song {video_id}",
        channel_name="Artist",
        views=1000,
        score=score,
    )


def make_source(videos: list[CanonicalVideo]) -> TrendingVideoFetcher:
    mock = create_autospec(TrendingVideoFetcher, instance=True)
    mock.fetch_trending_videos = AsyncMock(return_value=videos)
    return mock


class TestFetchTrendingUseCase:
    async def test_returns_videos_from_source(self) -> None:
        videos = [make_video("v1"), make_video("v2")]
        source = make_source(videos)
        use_case = FetchTrendingUseCase(source)

        result = await use_case.execute(FetchTrendingRequest(region="ES"))

        assert len(result.videos) == 2
        assert result.region == "ES"

    async def test_scored_videos_sorted_descending(self) -> None:
        videos = [make_video("v1", score=1.0), make_video("v2", score=5.0), make_video("v3", score=3.0)]
        source = make_source(videos)
        use_case = FetchTrendingUseCase(source)

        result = await use_case.execute(FetchTrendingRequest(region="ES"))

        scores = [v.score for v in result.videos]
        assert scores == sorted(scores, reverse=True)

    async def test_limit_is_respected(self) -> None:
        videos = [make_video(f"v{i}", score=float(i)) for i in range(20)]
        source = make_source(videos)
        use_case = FetchTrendingUseCase(source)

        result = await use_case.execute(FetchTrendingRequest(region="ES", limit=5))

        assert len(result.videos) == 5

    async def test_unscored_videos_included_after_scored(self) -> None:
        videos = [make_video("unscored1"), make_video("scored1", score=5.0)]
        source = make_source(videos)
        use_case = FetchTrendingUseCase(source)

        result = await use_case.execute(FetchTrendingRequest(region="ES"))

        assert result.videos[0].video_id == "scored1"
        assert result.videos[1].video_id == "unscored1"

    async def test_empty_source_returns_empty_result(self) -> None:
        source = make_source([])
        use_case = FetchTrendingUseCase(source)

        result = await use_case.execute(FetchTrendingRequest(region="US"))

        assert result.fetched_count == 0

    async def test_source_called_with_correct_region_and_date(self) -> None:
        source = make_source([])
        use_case = FetchTrendingUseCase(source)

        await use_case.execute(FetchTrendingRequest(region="MX", date="2026-03-31"))

        source.fetch_trending_videos.assert_awaited_once_with(region="MX", date="2026-03-31")
