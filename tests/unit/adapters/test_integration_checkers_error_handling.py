"""Integration checker error resilience tests.

Verify that all integration checkers (YouTube, Instagram, TikTok) return stable
IntegrationCheckResult(status=ERROR) when SDK calls raise exceptions, rather than
propagating exceptions or crashing.
"""

from __future__ import annotations

import pytest

from src.adapters.instagram_integration_checker import InstagramIntegrationChecker
from src.adapters.tiktok_integration_checker import TikTokIntegrationChecker
from src.adapters.youtube_integration_checker import YouTubeIntegrationChecker
from src.domain.models import IntegrationCheckStatus

# ─────────────────────────────────────────────────────────────────────────────
# YouTube Integration Checker Error Handling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_youtube_checker_returns_error_on_client_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify YouTube checker returns ERROR status when YTClient raises exception."""
    checker = YouTubeIntegrationChecker()
    monkeypatch.setattr(YouTubeIntegrationChecker, "is_configured", property(lambda _self: True))

    class _FailingClient:
        async def check_connection(self) -> None:
            raise RuntimeError("YouTube API quota exceeded")

    monkeypatch.setattr("src.adapters.youtube_integration_checker._build_yt_client", _FailingClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.is_configured is True
    assert "quota" in result.message.lower()


@pytest.mark.asyncio
async def test_youtube_checker_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify YouTube checker catches timeout exceptions."""
    checker = YouTubeIntegrationChecker()
    monkeypatch.setattr(YouTubeIntegrationChecker, "is_configured", property(lambda _self: True))

    class _TimeoutClient:
        async def check_connection(self) -> None:
            raise TimeoutError("Request timed out")

    monkeypatch.setattr("src.adapters.youtube_integration_checker._build_yt_client", _TimeoutClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message is not None


@pytest.mark.asyncio
async def test_youtube_checker_handles_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify YouTube checker catches auth-related exceptions."""
    checker = YouTubeIntegrationChecker()
    monkeypatch.setattr(YouTubeIntegrationChecker, "is_configured", property(lambda _self: True))

    class _AuthFailClient:
        async def check_connection(self) -> None:
            raise PermissionError("YouTube OAuth token expired or invalid")

    monkeypatch.setattr("src.adapters.youtube_integration_checker._build_yt_client", _AuthFailClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert "token" in result.message.lower() or "auth" in result.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Instagram Integration Checker Error Handling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_instagram_checker_returns_error_on_client_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Instagram checker returns ERROR status when InstagramClient raises exception."""
    checker = InstagramIntegrationChecker()
    monkeypatch.setattr(InstagramIntegrationChecker, "is_configured", property(lambda _self: True))

    class _FailingClient:
        async def check_connection(self) -> None:
            raise RuntimeError("Instagram session cookie invalid or expired")

    monkeypatch.setattr("src.adapters.instagram_integration_checker.InstagramClient", _FailingClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.is_configured is True
    assert "session" in result.message.lower() or "cookie" in result.message.lower()


@pytest.mark.asyncio
async def test_instagram_checker_handles_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Instagram checker catches network-related exceptions."""
    checker = InstagramIntegrationChecker()
    monkeypatch.setattr(InstagramIntegrationChecker, "is_configured", property(lambda _self: True))

    class _NetworkFailClient:
        async def check_connection(self) -> None:
            raise ConnectionError("Failed to connect to Instagram servers")

    monkeypatch.setattr("src.adapters.instagram_integration_checker.InstagramClient", _NetworkFailClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert "connect" in result.message.lower() or "connection" in result.message.lower()


@pytest.mark.asyncio
async def test_instagram_checker_handles_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify Instagram checker catches timeout exceptions."""
    checker = InstagramIntegrationChecker()
    monkeypatch.setattr(InstagramIntegrationChecker, "is_configured", property(lambda _self: True))

    class _TimeoutClient:
        async def check_connection(self) -> None:
            raise TimeoutError("Instagram request timed out")

    monkeypatch.setattr("src.adapters.instagram_integration_checker.InstagramClient", _TimeoutClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message is not None


# ─────────────────────────────────────────────────────────────────────────────
# TikTok Integration Checker Error Handling
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tiktok_checker_returns_error_on_client_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TikTok checker returns ERROR status when TikTokUploaderClient raises exception."""
    checker = TikTokIntegrationChecker()
    monkeypatch.setattr(TikTokIntegrationChecker, "is_configured", property(lambda _self: True))

    class _FailingClient:
        def check_connection(self) -> None:
            raise RuntimeError("TikTok cookies invalid or expired")

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.TikTokUploaderClient", _FailingClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.is_configured is True
    assert "cookies" in result.message.lower()


@pytest.mark.asyncio
async def test_tiktok_checker_handles_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TikTok checker catches authentication-related exceptions."""
    checker = TikTokIntegrationChecker()
    monkeypatch.setattr(TikTokIntegrationChecker, "is_configured", property(lambda _self: True))

    class _AuthFailClient:
        def check_connection(self) -> None:
            raise PermissionError("TikTok account not authorized")

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.TikTokUploaderClient", _AuthFailClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert "auth" in result.message.lower() or "permission" in result.message.lower()


@pytest.mark.asyncio
async def test_tiktok_checker_handles_network_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify TikTok checker catches network-related exceptions."""
    checker = TikTokIntegrationChecker()
    monkeypatch.setattr(TikTokIntegrationChecker, "is_configured", property(lambda _self: True))

    class _NetworkFailClient:
        def check_connection(self) -> None:
            raise ConnectionError("TikTok uploader cannot reach service")

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.TikTokUploaderClient", _NetworkFailClient)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message is not None
