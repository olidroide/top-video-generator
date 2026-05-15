from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models import VideoVerificationStatus


@pytest.mark.asyncio
async def test_verify_live_media() -> None:
    media = MagicMock()
    media.caption_text = "Test reel caption"

    with patch("src.adapters.instagram_video_verifier.InstagramClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_media_info = AsyncMock(return_value=media)
        mock_client_cls.return_value = mock_client

        from src.adapters.instagram_video_verifier import InstagramVideoVerifier

        verifier = InstagramVideoVerifier()
        result = await verifier.verify("3456789012")

        assert result.status == VideoVerificationStatus.LIVE
        assert result.release_id == "3456789012"
        assert result.title == "Test reel caption"
        assert "instagram.com/reel/3456789012" in result.url


@pytest.mark.asyncio
async def test_verify_not_found() -> None:
    with patch("src.adapters.instagram_video_verifier.InstagramClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_media_info = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        from src.adapters.instagram_video_verifier import InstagramVideoVerifier

        verifier = InstagramVideoVerifier()
        result = await verifier.verify("missing")

        assert result.status == VideoVerificationStatus.NOT_FOUND
        assert result.details == "Media not found"


@pytest.mark.asyncio
async def test_verify_auth_error() -> None:
    from src.infrastructure.social.instagram_client import InstagramLoginError

    with patch("src.adapters.instagram_video_verifier.InstagramClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_media_info = AsyncMock(side_effect=InstagramLoginError("Login failed"))
        mock_client_cls.return_value = mock_client

        from src.adapters.instagram_video_verifier import InstagramVideoVerifier

        verifier = InstagramVideoVerifier()
        result = await verifier.verify("auth_err")

        assert result.status == VideoVerificationStatus.ERROR
        assert "Auth failed" in result.details


@pytest.mark.asyncio
async def test_verify_generic_error() -> None:
    with patch("src.adapters.instagram_video_verifier.InstagramClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.get_media_info = AsyncMock(side_effect=RuntimeError("Network error"))
        mock_client_cls.return_value = mock_client

        from src.adapters.instagram_video_verifier import InstagramVideoVerifier

        verifier = InstagramVideoVerifier()
        result = await verifier.verify("err")

        assert result.status == VideoVerificationStatus.ERROR
        assert "Network error" in result.details


def test_platform_name() -> None:
    from src.adapters.instagram_video_verifier import InstagramVideoVerifier

    verifier = InstagramVideoVerifier()
    assert verifier.platform_name == "INSTAGRAM"
