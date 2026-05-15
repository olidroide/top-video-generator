"""Unit tests for publisher adapters (YouTube, TikTok, Instagram)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from src.domain.models import CanonicalVideo, Platform


def make_canonical_video(video_id: str = "v1") -> CanonicalVideo:
    return CanonicalVideo(
        video_id=video_id,
        title="Test Song",
        channel_name="Artist",
        views=1000,
        views_growth=0,
        score=0.0,
        score_previous=0.0,
        thumbnail_url=None,
        description="",
        duration_seconds=180.0,
        likes=100,
    )


_VIDEO_LIST = [make_canonical_video()]


# ---------------------------------------------------------------------------
# YouTubePublisher
# ---------------------------------------------------------------------------


class TestYouTubePublisher:
    async def test_publish_success(self) -> None:
        from src.adapters.youtube_publisher import YouTubePublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(return_value="yt_video_id")

        with patch("src.adapters.youtube_publisher._build_yt_client", return_value=mock_client):
            publisher = YouTubePublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Top Songs",
                description="Weekly top",
            )

        assert result.success is True
        assert result.published_id == "yt_video_id"
        assert result.platform == Platform.YOUTUBE

    async def test_publish_forwards_upload_arguments(self) -> None:
        from src.adapters.youtube_publisher import YouTubePublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(return_value="yt_video_id")

        with patch("src.adapters.youtube_publisher._build_yt_client", return_value=mock_client):
            publisher = YouTubePublisher()
            await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Top Songs",
                description="Weekly top",
            )

        mock_client.upload_video.assert_awaited_once_with(
            "/tmp/video.mp4",
            "Top Songs",
            "Weekly top",
        )

    async def test_publish_failure_returns_error_result(self) -> None:
        from src.adapters.youtube_publisher import YouTubePublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(side_effect=RuntimeError("upload failed"))

        with patch("src.adapters.youtube_publisher._build_yt_client", return_value=mock_client):
            publisher = YouTubePublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Top Songs",
                description="Weekly top",
            )

        assert result.success is False
        assert "upload failed" in (result.error or "")
        assert result.platform == Platform.YOUTUBE

    async def test_publish_none_id_returns_error_result(self) -> None:
        from src.adapters.youtube_publisher import YouTubePublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(return_value=None)

        with patch("src.adapters.youtube_publisher._build_yt_client", return_value=mock_client):
            publisher = YouTubePublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Top Songs",
                description="Weekly top",
            )

        assert result.success is False
        assert "no media id" in (result.error or "")
        assert result.platform == Platform.YOUTUBE

    def test_platform_name(self) -> None:
        from src.adapters.youtube_publisher import YouTubePublisher

        publisher = YouTubePublisher()
        assert publisher.platform_name == Platform.YOUTUBE


# ---------------------------------------------------------------------------
# TikTokPublisher
# ---------------------------------------------------------------------------


class TestTikTokPublisher:
    async def test_publish_success(self) -> None:
        from src.adapters.tiktok_publisher import TikTokPublisher

        mock_client = MagicMock()
        mock_client.upload_video = MagicMock(return_value="tt_video_id")

        with patch("src.adapters.tiktok_publisher.TikTokUploaderClient", return_value=mock_client):
            publisher = TikTokPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Weekly top",
                description="",
            )

        assert result.success is True
        assert result.published_id == "tt_video_id"
        assert result.platform == Platform.TIKTOK

    async def test_publish_failure_returns_error_result(self) -> None:
        from src.adapters.tiktok_publisher import TikTokPublisher

        mock_client = MagicMock()
        mock_client.upload_video = MagicMock(side_effect=RuntimeError("tiktok error"))

        with patch("src.adapters.tiktok_publisher.TikTokUploaderClient", return_value=mock_client):
            publisher = TikTokPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Weekly top",
                description="",
            )

        assert result.success is False
        assert "tiktok error" in (result.error or "")

    async def test_publish_none_id_returns_error_result(self) -> None:
        from src.adapters.tiktok_publisher import TikTokPublisher

        mock_client = MagicMock()
        mock_client.upload_video = MagicMock(return_value=None)

        with patch("src.adapters.tiktok_publisher.TikTokUploaderClient", return_value=mock_client):
            publisher = TikTokPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Weekly top",
                description="",
            )

        assert result.success is False
        assert "no media id" in (result.error or "")
        assert result.platform == Platform.TIKTOK

    def test_platform_name(self) -> None:
        from src.adapters.tiktok_publisher import TikTokPublisher

        publisher = TikTokPublisher()
        assert publisher.platform_name == Platform.TIKTOK


# ---------------------------------------------------------------------------
# InstagramPublisher
# ---------------------------------------------------------------------------


class TestInstagramPublisher:
    async def test_publish_success(self) -> None:
        from src.adapters.instagram_publisher import InstagramPublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(return_value="ig_media_id")

        with patch("src.adapters.instagram_publisher.InstagramClient", return_value=mock_client):
            publisher = InstagramPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Reel caption",
                description="",
            )

        assert result.success is True
        assert result.published_id == "ig_media_id"
        assert result.platform == Platform.INSTAGRAM

    async def test_publish_failure_returns_error_result(self) -> None:
        from src.adapters.instagram_publisher import InstagramPublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(side_effect=RuntimeError("instagram down"))

        with patch("src.adapters.instagram_publisher.InstagramClient", return_value=mock_client):
            publisher = InstagramPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Reel caption",
                description="",
            )

        assert result.success is False
        assert "instagram down" in (result.error or "")

    async def test_publish_none_id_returns_error_result(self) -> None:
        from src.adapters.instagram_publisher import InstagramPublisher

        mock_client = MagicMock()
        mock_client.upload_video = AsyncMock(return_value=None)

        with patch("src.adapters.instagram_publisher.InstagramClient", return_value=mock_client):
            publisher = InstagramPublisher()
            result = await publisher.publish_video(
                video_list=_VIDEO_LIST,
                file_path="/tmp/video.mp4",
                title="Reel caption",
                description="",
            )

        assert result.success is False
        assert "no media id" in (result.error or "")
        assert result.platform == Platform.INSTAGRAM

    def test_platform_name(self) -> None:
        from src.adapters.instagram_publisher import InstagramPublisher

        publisher = InstagramPublisher()
        assert publisher.platform_name == Platform.INSTAGRAM

    def test_is_disabled_when_optional_dependency_is_missing(self) -> None:
        from src.adapters.instagram_publisher import InstagramPublisher

        class _Settings:
            instagram_client_username = "configured-user"

        with (
            patch("src.adapters.instagram_publisher.get_app_settings", return_value=_Settings()),
            patch("src.adapters.instagram_publisher.is_instagrapi_available", return_value=False),
        ):
            publisher = InstagramPublisher()
            assert publisher.is_enabled is False
