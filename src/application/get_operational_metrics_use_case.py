"""Use case for reading persisted operational metrics for admin SSR."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports import OperationalMetricsReader


@dataclass(frozen=True)
class OperationalMetricsResult:
    """Flattened counters used by the admin metrics panel."""

    fetch_count: int
    fetch_errors: int
    upload_count: int
    upload_errors: int
    processing_count: int
    processing_errors: int

    def to_dict(self) -> dict[str, int]:
        return {
            "fetch_count": self.fetch_count,
            "fetch_errors": self.fetch_errors,
            "upload_count": self.upload_count,
            "upload_errors": self.upload_errors,
            "processing_count": self.processing_count,
            "processing_errors": self.processing_errors,
        }


class GetOperationalMetricsUseCase:
    """Read persisted metrics in a fixed time window for admin observability."""

    def __init__(self, metrics_reader: OperationalMetricsReader, *, window_hours: int = 24) -> None:
        self._metrics_reader = metrics_reader
        self._window_hours = window_hours

    def execute(self) -> OperationalMetricsResult:
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=self._window_hours)
        counts = self._metrics_reader.get_metric_counts(start_time=start_time, end_time=end_time)

        return OperationalMetricsResult(
            fetch_count=counts.get("fetch", {}).get("count", 0),
            fetch_errors=counts.get("fetch", {}).get("errors", 0),
            upload_count=counts.get("upload", {}).get("count", 0),
            upload_errors=counts.get("upload", {}).get("errors", 0),
            processing_count=counts.get("processing", {}).get("count", 0),
            processing_errors=counts.get("processing", {}).get("errors", 0),
        )
