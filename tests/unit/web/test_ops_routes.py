"""Unit tests for web operational routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi.testclient import TestClient

from src.config.settings import AppSettings
from src.web.dependencies import get_timeseries_repo
from src.web.main import create_app

app = create_app(AppSettings(yt_search_region_code="ES"))


@dataclass
class _TimeSeriesRepoStub:
    def get_points_by_date_range(self, _from_dt: datetime, _until_dt: datetime) -> list[object]:
        return []


def test_health_returns_structured_checks() -> None:
    app.dependency_overrides[get_timeseries_repo] = lambda: _TimeSeriesRepoStub()

    with TestClient(app) as client:
        response = client.get("/health")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert "checks" in body
    assert set(body["checks"].keys()) == {"ffmpeg", "templates", "database"}


def test_metrics_routes_are_not_exposed() -> None:
    with TestClient(app) as client:
        read_response = client.get("/metrics")
        write_response = client.post("/metrics/increment/fetch")

    assert read_response.status_code == 404
    assert write_response.status_code == 404
