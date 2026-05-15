from __future__ import annotations

import pytest

from src.adapters.tiktok_integration_checker import TikTokIntegrationChecker
from src.domain.models import IntegrationCheckStatus


@pytest.mark.asyncio
async def test_tiktok_checker_not_configured_when_dependency_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = TikTokIntegrationChecker()

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.is_tiktok_uploader_available", lambda: False)
    monkeypatch.setattr(
        "src.adapters.tiktok_integration_checker.get_app_settings",
        lambda: pytest.fail("settings should not be loaded when dependency is missing"),
    )

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.NOT_CONFIGURED
    assert result.message is not None
    assert "dependency" in result.message.lower()


@pytest.mark.asyncio
async def test_tiktok_checker_reports_ok_when_uploader_initializes(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = TikTokIntegrationChecker()

    monkeypatch.setattr(TikTokIntegrationChecker, "is_configured", property(lambda _self: True))

    class _Client:
        def check_connection(self) -> bool:
            return True

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.TikTokUploaderClient", _Client)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.OK
    assert result.message == "TikTok uploader dependency and cookies are ready."


@pytest.mark.asyncio
async def test_tiktok_checker_reports_error_when_uploader_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = TikTokIntegrationChecker()

    monkeypatch.setattr(TikTokIntegrationChecker, "is_configured", property(lambda _self: True))

    class _Client:
        def check_connection(self) -> bool:
            raise RuntimeError("invalid cookies")

    monkeypatch.setattr("src.adapters.tiktok_integration_checker.TikTokUploaderClient", _Client)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message == "invalid cookies"
