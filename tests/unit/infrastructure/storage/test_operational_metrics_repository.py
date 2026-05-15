from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from src.infrastructure.storage.operational_metrics_repository import OperationalMetricsRepository


def test_record_and_read_metric_counts(tmp_path) -> None:
    db_path = tmp_path / "timeseries.csv"
    repo = OperationalMetricsRepository(str(db_path))

    now = datetime.now(UTC)
    repo.record_metric_event(stage="fetch", is_error=False, event_time=now - timedelta(minutes=5))
    repo.record_metric_event(stage="fetch", is_error=True, event_time=now - timedelta(minutes=4))
    repo.record_metric_event(stage="upload", is_error=False, event_time=now - timedelta(minutes=3))

    counts = repo.get_metric_counts(start_time=now - timedelta(hours=1), end_time=now)

    assert counts["fetch"]["count"] == 1
    assert counts["fetch"]["errors"] == 1
    assert counts["upload"]["count"] == 1
    assert counts["upload"]["errors"] == 0
    assert counts["processing"]["count"] == 0
    repo.close()


def test_record_metric_event_rejects_unsupported_stage(tmp_path) -> None:
    repo = OperationalMetricsRepository(str(tmp_path / "timeseries.csv"))

    with pytest.raises(ValueError, match="Unsupported metrics stage"):
        repo.record_metric_event(stage="unknown", is_error=False)

    repo.close()


def test_retention_prunes_old_metric_events(tmp_path) -> None:
    db_path = tmp_path / "timeseries.csv"
    repo = OperationalMetricsRepository(str(db_path), retention_days=30)

    now = datetime.now(UTC)
    repo.record_metric_event(stage="fetch", is_error=False, event_time=now - timedelta(days=40))
    repo.record_metric_event(stage="fetch", is_error=False, event_time=now - timedelta(minutes=1))

    counts = repo.get_metric_counts(start_time=now - timedelta(days=90), end_time=now + timedelta(minutes=1))

    assert counts["fetch"]["count"] == 1
    assert counts["fetch"]["errors"] == 0
    repo.close()


def test_repository_creates_missing_parent_directory(tmp_path) -> None:
    db_path = tmp_path / "missing" / "nested" / "timeseries.csv"

    repo = OperationalMetricsRepository(str(db_path))
    repo.record_metric_event(stage="fetch", is_error=False)

    assert db_path.exists()
    repo.close()
