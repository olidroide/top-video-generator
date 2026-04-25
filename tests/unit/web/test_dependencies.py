from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from src.web.dependencies import get_spotify_provider, get_tiktok_provider, get_yt_client

if TYPE_CHECKING:
    import pytest


class _ProductionClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _FakeClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _TikTokClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _SpotifyClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


def test_get_yt_client_returns_production_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.YTClient", _ProductionClient)
    monkeypatch.setattr("src.web.dependencies.YTClientFake", _FakeClient)
    settings = SimpleNamespace(is_production_env=True)

    client = get_yt_client(settings)

    assert isinstance(client, _ProductionClient)
    assert client.settings is settings


def test_get_yt_client_returns_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.YTClient", _ProductionClient)
    monkeypatch.setattr("src.web.dependencies.YTClientFake", _FakeClient)
    settings = SimpleNamespace(is_production_env=False)

    client = get_yt_client(settings)

    assert isinstance(client, _FakeClient)
    assert client.settings is settings


def test_get_tiktok_provider_passes_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.TikTokClient", _TikTokClient)
    settings = SimpleNamespace()

    client = get_tiktok_provider(settings)

    assert isinstance(client, _TikTokClient)
    assert client.settings is settings


def test_get_spotify_provider_passes_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.SpotifyClient", _SpotifyClient)
    settings = SimpleNamespace()

    client = get_spotify_provider(settings)

    assert isinstance(client, _SpotifyClient)
    assert client.settings is settings
