"""Unit tests for YouTubeSource adapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.youtube_source import YouTubeSource
from src.infrastructure.youtube.schemas import (
    YTRoot,
    YTThumbnail,
    YTVideContentStatistics,
    YTVideo,
    YTVideoContentDetails,
    YTVideoSnippet,
    YTVideoSnippetThumbnail,
)


def make_yt_video(
    video_id: str = "abc123",
    title: str = "Test Song",
    channel: str = "Artist",
    views: int = 1_000_000,
    likes: int = 50_000,
    duration: str = "PT3M30S",
    thumbnail_url: str = "https://example.com/thumb.jpg",
) -> YTVideo:
    return YTVideo(
        kind="youtube#video",
        etag="etag",
        id=video_id,
        snippet=YTVideoSnippet(
            title=title,
            channelTitle=channel,
            description="Some description",
            thumbnails=YTVideoSnippetThumbnail(high=YTThumbnail(url=thumbnail_url, width=480, height=360)),
        ),
        statistics=YTVideContentStatistics(viewCount=views, likeCount=likes),
        contentDetails=YTVideoContentDetails(duration=duration),
    )


def make_yt_root(videos: list[YTVideo]) -> YTRoot:
    return YTRoot(
        kind="youtube#videoListResponse",
        etag="etag",
        pageInfo=None,
        items=videos,
    )


class TestYouTubeSourceFetchTrending:
    async def test_returns_canonical_videos(self) -> None:
        mock_client = MagicMock()
        mock_client.get_popular_videos = AsyncMock(return_value=make_yt_root([make_yt_video("v1")]))

        with patch("src.adapters.youtube_source.YTClient", return_value=mock_client):
            source = YouTubeSource()
            source.client = mock_client
            results = await source.fetch_trending_videos()

        assert len(results) == 1
        assert results[0].video_id == "v1"
        assert results[0].title == "Test Song"

    async def test_maps_views_and_likes(self) -> None:
        video = make_yt_video("v2", views=2_000_000, likes=100_000)
        mock_client = MagicMock()
        mock_client.get_popular_videos = AsyncMock(return_value=make_yt_root([video]))

        source = YouTubeSource()
        source.client = mock_client
        results = await source.fetch_trending_videos()

        assert results[0].views == 2_000_000
        assert results[0].likes == 100_000

    async def test_maps_duration_seconds(self) -> None:
        video = make_yt_video("v3", duration="PT4M15S")
        mock_client = MagicMock()
        mock_client.get_popular_videos = AsyncMock(return_value=make_yt_root([video]))

        source = YouTubeSource()
        source.client = mock_client
        results = await source.fetch_trending_videos()

        assert results[0].duration_seconds == pytest.approx(255.0)

    async def test_handles_missing_snippet(self) -> None:
        video = YTVideo(kind="youtube#video", etag="etag", id="no_snippet")
        mock_client = MagicMock()
        mock_client.get_popular_videos = AsyncMock(return_value=make_yt_root([video]))

        source = YouTubeSource()
        source.client = mock_client
        results = await source.fetch_trending_videos()

        assert results[0].title == ""
        assert results[0].views == 0

    async def test_returns_multiple_videos(self) -> None:
        videos = [make_yt_video(f"v{i}") for i in range(5)]
        mock_client = MagicMock()
        mock_client.get_popular_videos = AsyncMock(return_value=make_yt_root(videos))

        source = YouTubeSource()
        source.client = mock_client
        results = await source.fetch_trending_videos(limit=5)

        assert len(results) == 5
