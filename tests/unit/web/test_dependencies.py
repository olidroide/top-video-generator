from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from src.web.dependencies import get_yt_client

if TYPE_CHECKING:
    import pytest


class _ProductionClient:
    pass


class _FakeClient:
    pass


def test_get_yt_client_returns_production_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.get_app_settings", lambda: SimpleNamespace(is_production_env=True))
    monkeypatch.setattr("src.web.dependencies.YTClient", _ProductionClient)
    monkeypatch.setattr("src.web.dependencies.YTClientFake", _FakeClient)

    client = get_yt_client()

    assert isinstance(client, _ProductionClient)


def test_get_yt_client_returns_fake_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.get_app_settings", lambda: SimpleNamespace(is_production_env=False))
    monkeypatch.setattr("src.web.dependencies.YTClient", _ProductionClient)
    monkeypatch.setattr("src.web.dependencies.YTClientFake", _FakeClient)

    client = get_yt_client()

    assert isinstance(client, _FakeClient)
