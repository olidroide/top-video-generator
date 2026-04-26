from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Self
from unittest.mock import Mock

import pytest

from src.infrastructure.social.spotify_client import SpotifyClient, get_default_client
from src.infrastructure.social.spotipy_exceptions import SpotifyPermissionError


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


def test_spotify_client_configures_requests_session_verify_from_cert_bundle(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    class _FakeSpotifyOAuth:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            captured["kwargs"] = kwargs

    monkeypatch.setattr("src.infrastructure.social.spotify_client.SpotifyOAuth", _FakeSpotifyOAuth)
    monkeypatch.setattr(
        "src.infrastructure.social.spotify_client.configure_process_wide_certifi_bundle",
        lambda _settings: "/tmp/company-ca.pem",
    )

    settings = SimpleNamespace(
        spotify_client_id="cid",
        spotify_client_secret="secret",
        spotify_redirect_uri="http://127.0.0.1:8080/spotify_auth/",
        spotify_user_id="sp-user",
        db_auth_file=str(tmp_path / "auth.json"),
    )

    SpotifyClient(settings)

    kwargs = captured["kwargs"]
    requests_session = kwargs["requests_session"]
    assert requests_session.verify == "/tmp/company-ca.pem"


@pytest.mark.asyncio
async def test_spotify_exchange_code_uses_fallback_user_id_when_me_fails(monkeypatch, tmp_path) -> None:
    class _FakeSpotifyOAuth:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            del kwargs

        def get_access_token(self, _authorization_value, **kwargs) -> dict[str, str]:  # type: ignore[no-untyped-def]
            del kwargs
            return {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "scope": "playlist-modify-private",
            }

    monkeypatch.setattr("src.infrastructure.social.spotify_client.SpotifyOAuth", _FakeSpotifyOAuth)
    monkeypatch.setattr(
        "src.infrastructure.social.spotify_client.configure_process_wide_certifi_bundle",
        lambda _settings: None,
    )

    settings = SimpleNamespace(
        spotify_client_id="cid",
        spotify_client_secret="secret",
        spotify_redirect_uri="http://127.0.0.1:8080/spotify_auth/",
        spotify_user_id="fallback-user",
        db_auth_file=str(tmp_path / "auth.json"),
    )
    client = SpotifyClient(settings)

    async def _raise_permission_error(*, user_access_token: str | None = None) -> dict[str, object]:
        del user_access_token
        raise SpotifyPermissionError("Insufficient scope")

    monkeypatch.setattr(client, "fetch_user_info", _raise_permission_error)

    auth = await client.step_2_exchange_code_authentication("auth-code")

    assert auth.client_id == "fallback-user"
    assert auth.refresh_token == "refresh-token"
