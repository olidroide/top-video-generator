"""Tests for GetOperationalMetricsUseCase."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.application.get_operational_metrics_use_case import GetOperationalMetricsUseCase


def test_execute_maps_persisted_counts_to_flat_result() -> None:
    metrics_reader = MagicMock(spec=["get_metric_counts"])
    metrics_reader.get_metric_counts.return_value = {
        "fetch": {"count": 10, "errors": 2},
        "processing": {"count": 7, "errors": 1},
        "upload": {"count": 3, "errors": 0},
    }

    use_case = GetOperationalMetricsUseCase(metrics_reader, window_hours=24)
    result = use_case.execute()

    assert result.fetch_count == 10
    assert result.fetch_errors == 2
    assert result.processing_count == 7
    assert result.processing_errors == 1
    assert result.upload_count == 3
    assert result.upload_errors == 0


def test_execute_defaults_missing_stage_to_zero() -> None:
    metrics_reader = MagicMock(spec=["get_metric_counts"])
    metrics_reader.get_metric_counts.return_value = {
        "fetch": {"count": 1, "errors": 0},
    }

    use_case = GetOperationalMetricsUseCase(metrics_reader)
    result = use_case.execute()

    assert result.fetch_count == 1
    assert result.fetch_errors == 0
    assert result.processing_count == 0
    assert result.processing_errors == 0
    assert result.upload_count == 0
    assert result.upload_errors == 0
