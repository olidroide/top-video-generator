from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import VideoVerificationStatus


@pytest.mark.asyncio
async def test_verify_live_video() -> None:
    video = MagicMock()
    video.status.upload_status = "processed"
    video.status.privacy_status = "public"
    video.snippet.title = "Test Video"

    details = MagicMock()
    details.items = [video]

    with patch("src.adapters.youtube_video_verifier._build_yt_client") as mock_build:
        mock_client = AsyncMock()
        mock_client.get_video_details = AsyncMock(return_value=details)
        mock_build.return_value = mock_client

        from src.adapters.youtube_video_verifier import YouTubeVideoVerifier

        verifier = YouTubeVideoVerifier()
        result = await verifier.verify("abc123")

        assert result.status == VideoVerificationStatus.LIVE
        assert result.release_id == "abc123"
        assert result.title == "Test Video"
        assert "youtube.com/watch?v=abc123" in result.url


@pytest.mark.asyncio
async def test_verify_processing_video() -> None:
    video = MagicMock()
    video.status.upload_status = "uploaded"
    video.status.privacy_status = "public"
    video.snippet.title = "Processing Video"

    details = MagicMock()
    details.items = [video]

    with patch("src.adapters.youtube_video_verifier._build_yt_client") as mock_build:
        mock_client = AsyncMock()
        mock_client.get_video_details = AsyncMock(return_value=details)
        mock_build.return_value = mock_client

        from src.adapters.youtube_video_verifier import YouTubeVideoVerifier

        verifier = YouTubeVideoVerifier()
        result = await verifier.verify("def456")

        assert result.status == VideoVerificationStatus.PROCESSING
        assert result.release_id == "def456"


@pytest.mark.asyncio
async def test_verify_not_found() -> None:
    details = MagicMock()
    details.items = []

    with patch("src.adapters.youtube_video_verifier._build_yt_client") as mock_build:
        mock_client = AsyncMock()
        mock_client.get_video_details = AsyncMock(return_value=details)
        mock_build.return_value = mock_client

        from src.adapters.youtube_video_verifier import YouTubeVideoVerifier

        verifier = YouTubeVideoVerifier()
        result = await verifier.verify("nonexistent")

        assert result.status == VideoVerificationStatus.NOT_FOUND
        assert result.details == "Video not found in YouTube API"


@pytest.mark.asyncio
async def test_verify_error() -> None:
    with patch("src.adapters.youtube_video_verifier._build_yt_client") as mock_build:
        mock_client = AsyncMock()
        mock_client.get_video_details = AsyncMock(side_effect=Exception("API error"))
        mock_build.return_value = mock_client

        from src.adapters.youtube_video_verifier import YouTubeVideoVerifier

        verifier = YouTubeVideoVerifier()
        result = await verifier.verify("err123")

        assert result.status == VideoVerificationStatus.ERROR
        assert "API error" in result.details


def test_platform_name() -> None:
    from src.adapters.youtube_video_verifier import YouTubeVideoVerifier

    verifier = YouTubeVideoVerifier()
    assert verifier.platform_name == "YOUTUBE"
