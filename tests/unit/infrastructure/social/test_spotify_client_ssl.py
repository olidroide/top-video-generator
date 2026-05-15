from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Self
from unittest.mock import AsyncMock, Mock

import pytest

from src.infrastructure.social.spotify_client import SpotifyClient, get_default_client
from src.infrastructure.social.spotipy_exceptions import SpotifyAuthError, SpotifyClientError, SpotifyPermissionError


def _spotify_settings(tmp_path) -> SimpleNamespace:
    return SimpleNamespace(
        spotify_client_id="cid",
        spotify_client_secret="secret",
        spotify_redirect_uri="http://127.0.0.1:8080/spotify_auth/",
        spotify_user_id="sp-user",
        db_auth_file=str(tmp_path / "auth.json"),
        ca_bundle_file=None,
        use_certifi=False,
    )


@pytest.fixture(autouse=True)
def _disable_process_wide_cert_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.infrastructure.social.spotify_client.configure_process_wide_certifi_bundle",
        lambda _settings: None,
    )


class _FakeClientSession:
    def __init__(self, *, connector: object, timeout: object) -> None:
        self.connector = connector
        self.timeout = timeout

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


def test_get_default_client_builds_connector_with_ssl_context(monkeypatch) -> None:
    fake_context = object()
    build_ssl_context_mock = Mock(return_value=fake_context)
    monkeypatch.setattr(
        "src.infrastructure.social.spotify_client.build_ssl_context",
        build_ssl_context_mock,
    )

    captured_ssl: dict[str, object] = {}

    def _fake_tcp_connector(*, ssl: object) -> object:
        captured_ssl["value"] = ssl
        return SimpleNamespace(ssl=ssl)

    monkeypatch.setattr("src.infrastructure.social.spotify_client.aiohttp.TCPConnector", _fake_tcp_connector)
    monkeypatch.setattr("src.infrastructure.social.spotify_client.aiohttp.ClientSession", _FakeClientSession)

    settings = SimpleNamespace(use_certifi=True)

    async def _run() -> None:
        async with get_default_client(settings) as client:
            assert client.connector is not None

    asyncio.run(_run())

    build_ssl_context_mock.assert_called_once_with(
        settings,
    )
    assert captured_ssl["value"] is fake_context


@pytest.mark.asyncio
async def test_spotify_step_1_returns_empty_url_when_oauth_is_unsupported(tmp_path) -> None:
    settings = _spotify_settings(tmp_path)
    client = SpotifyClient(settings)

    auth_url = await client.step_1_get_authentication_url()

    assert auth_url == ""


@pytest.mark.asyncio
async def test_spotify_step_2_raises_auth_error_when_oauth_is_unsupported(tmp_path) -> None:
    settings = _spotify_settings(tmp_path)
    client = SpotifyClient(settings)

    with pytest.raises(SpotifyAuthError):
        await client.step_2_exchange_code_authentication("auth-code")


@pytest.mark.asyncio
async def test_fetch_user_info_returns_synthetic_user_id_on_success(monkeypatch, tmp_path) -> None:
    class _FakeSpotipyFreeClient:
        def search(self, *, query: str, limit: int, **kwargs) -> dict[str, object]:
            assert query == "test"
            assert kwargs["type"] == "track"
            assert limit == 1
            return {"tracks": {"items": []}}

    settings = _spotify_settings(tmp_path)
    client = SpotifyClient(settings)
    monkeypatch.setattr(client, "_build_spotify_client", lambda: _FakeSpotipyFreeClient())

    user_info = await client.fetch_user_info()

    assert user_info["id"] == "sp-user"


@pytest.mark.asyncio
async def test_fetch_user_info_raises_clear_error_when_spotify_extra_is_missing(monkeypatch, tmp_path) -> None:
    settings = _spotify_settings(tmp_path)
    client = SpotifyClient(settings)

    def _raise_missing_module() -> None:
        raise ModuleNotFoundError("No module named 'SpotipyFree'")

    monkeypatch.setattr("src.infrastructure.social.spotify_client.import_module", lambda _name: _raise_missing_module())

    with pytest.raises(SpotifyClientError, match="Install Spotify support"):
        await client.fetch_user_info()


@pytest.mark.asyncio
async def test_update_original_playlist_raises_permission_error_when_write_unsupported(monkeypatch, tmp_path) -> None:
    settings = _spotify_settings(tmp_path)
    client = SpotifyClient(settings)

    monkeypatch.setattr(client, "search_for_track", AsyncMock(return_value={"id": "track-1"}))

    with pytest.raises(SpotifyPermissionError):
        await client.update_link_original_playlist("playlist-1", ["song title"])
