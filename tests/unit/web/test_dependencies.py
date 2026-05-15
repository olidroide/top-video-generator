from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from src.web.dependencies import (
    get_operational_metrics_repo,
    get_operational_metrics_use_case,
    get_spotify_provider,
    get_yt_client,
)

if TYPE_CHECKING:
    import pytest


class _ProductionClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _FakeClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _SpotifyClient:
    def __init__(self, settings: object | None = None) -> None:
        self.settings = settings


class _OperationalMetricsRepo:
    def __init__(self, db_path: str, *, retention_days: int | None = None) -> None:
        self.db_path = db_path
        self.retention_days = retention_days


class _OperationalMetricsUseCase:
    def __init__(self, metrics_repo: object, *, window_hours: int = 24) -> None:
        self.metrics_repo = metrics_repo
        self.window_hours = window_hours


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


def test_get_spotify_provider_passes_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.SpotifyClient", _SpotifyClient)
    settings = SimpleNamespace()

    client = get_spotify_provider(settings)

    assert isinstance(client, _SpotifyClient)
    assert client.settings is settings


def test_get_operational_metrics_repo_uses_production_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.TinyFluxOperationalMetricsRepository", _OperationalMetricsRepo)
    settings = SimpleNamespace(
        is_production_env=True,
        db_timeseries_file="db/db_timeseries.csv",
        operational_metrics_retention_days=90,
    )

    repo = get_operational_metrics_repo(settings)

    assert isinstance(repo, _OperationalMetricsRepo)
    assert repo.db_path == "db/db_timeseries.csv"
    assert repo.retention_days == 90


def test_get_operational_metrics_repo_uses_test_path_in_non_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.TinyFluxOperationalMetricsRepository", _OperationalMetricsRepo)
    settings = SimpleNamespace(
        is_production_env=False,
        db_timeseries_file="db/db_timeseries.csv",
        operational_metrics_retention_days=30,
    )

    repo = get_operational_metrics_repo(settings)

    assert isinstance(repo, _OperationalMetricsRepo)
    assert repo.db_path == "db/db_timeseries.csv.test"
    assert repo.retention_days == 30


def test_get_operational_metrics_use_case_uses_configured_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.dependencies.GetOperationalMetricsUseCase", _OperationalMetricsUseCase)
    settings = SimpleNamespace(operational_metrics_window_hours=48)
    repo = object()

    use_case = get_operational_metrics_use_case(repo, settings)

    assert isinstance(use_case, _OperationalMetricsUseCase)
    assert use_case.metrics_repo is repo
    assert use_case.window_hours == 48
