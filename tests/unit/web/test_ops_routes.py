"""Unit tests for web operational routes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi.testclient import TestClient

from src.web.dependencies import get_timeseries_repo
from src.web.main import app
from src.web.state import metrics_state


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


def test_metrics_increment_updates_known_metric() -> None:
    metrics_state["fetch_count"] = 0

    with TestClient(app) as client:
        response = client.post("/metrics/increment/fetch")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert metrics_state["fetch_count"] == 1


def test_metrics_increment_invalid_metric_returns_400() -> None:
    with TestClient(app) as client:
        response = client.post("/metrics/increment/not-a-real-metric")

    assert response.status_code == 400
    assert "metric" in response.json()["detail"].lower()
