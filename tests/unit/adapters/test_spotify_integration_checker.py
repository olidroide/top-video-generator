from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.adapters.spotify_integration_checker import SpotifyIntegrationChecker
from src.domain.models import IntegrationCheckStatus


@pytest.mark.asyncio
async def test_spotify_checker_surfaces_spotify_api_error_message(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = SpotifyIntegrationChecker()

    monkeypatch.setattr(SpotifyIntegrationChecker, "is_configured", property(lambda _self: True))

    fake_client = AsyncMock()
    fake_client.check_connection.return_value = {
        "error": {
            "status": 500,
            "message": "Unexpected upstream failure",
        }
    }

    monkeypatch.setattr("src.adapters.spotify_integration_checker.SpotifyClient", lambda: fake_client)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message == "Spotify API error: Unexpected upstream failure"


@pytest.mark.asyncio
async def test_spotify_checker_suggests_reauth_for_refresh_token_error(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = SpotifyIntegrationChecker()

    monkeypatch.setattr(SpotifyIntegrationChecker, "is_configured", property(lambda _self: True))

    fake_client = AsyncMock()
    fake_client.check_connection.return_value = {
        "error": {
            "status": 400,
            "message": "refresh_token must be supplied",
        }
    }

    monkeypatch.setattr("src.adapters.spotify_integration_checker.SpotifyClient", lambda: fake_client)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message is not None
    assert result.message.startswith("Spotify authorization is invalid or expired.")


@pytest.mark.asyncio
async def test_spotify_checker_suggests_reauth_for_invalid_bearer_error(monkeypatch: pytest.MonkeyPatch) -> None:
    checker = SpotifyIntegrationChecker()

    monkeypatch.setattr(SpotifyIntegrationChecker, "is_configured", property(lambda _self: True))

    fake_client = AsyncMock()
    fake_client.check_connection.return_value = {
        "error": {
            "status": 400,
            "message": "Only valid bearer authentication supported",
        }
    }

    monkeypatch.setattr("src.adapters.spotify_integration_checker.SpotifyClient", lambda: fake_client)

    result = await checker.check_connection()

    assert result.status is IntegrationCheckStatus.ERROR
    assert result.message is not None
    assert result.message.startswith("Spotify authorization is invalid or expired.")
