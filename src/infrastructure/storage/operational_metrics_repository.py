"""Operational metrics repository backed by TinyFlux."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from tinyflux import Point, TimeQuery, TinyFlux


class OperationalMetricsRepository:
    """Persist and aggregate operational metric events in TinyFlux."""

    _MEASUREMENT = "Operational metrics"
    _SUPPORTED_STAGES = frozenset({"fetch", "processing", "upload"})

    def __init__(self, db_path: str, *, retention_days: int | None = None) -> None:
        self._db = TinyFlux(db_path)
        self._retention_days = retention_days
        db_file = Path(db_path)
        self._lock_path = db_file.with_suffix(f"{db_file.suffix}.lock")

    def record_metric_event(
        self,
        *,
        stage: str,
        is_error: bool,
        event_time: datetime | None = None,
    ) -> None:
        if stage not in self._SUPPORTED_STAGES:
            msg = f"Unsupported metrics stage: {stage}"
            raise ValueError(msg)

        point_time = (event_time or datetime.now(UTC)).astimezone(UTC)
        with self._acquire_lock():
            self._db.insert(
                Point(
                    measurement=self._MEASUREMENT,
                    time=point_time,
                    tags={
                        "stage": stage,
                        "outcome": "error" if is_error else "success",
                    },
                    fields={"count": 1},
                )
            )
            self._prune_old_events()

    def get_metric_counts(self, *, start_time: datetime, end_time: datetime) -> dict[str, dict[str, int]]:
        query = (TimeQuery() > start_time.astimezone(UTC)) & (TimeQuery() <= end_time.astimezone(UTC))
        with self._acquire_lock():
            points = self._db.search(query)

        counts = {
            "fetch": {"count": 0, "errors": 0},
            "processing": {"count": 0, "errors": 0},
            "upload": {"count": 0, "errors": 0},
        }

        for point in points:
            if point.measurement != self._MEASUREMENT:
                continue

            stage = point.tags.get("stage") or ""
            outcome = point.tags.get("outcome") or "success"
            if stage not in counts:
                continue

            count_value = int(point.fields.get("count", 1) or 1)
            if outcome == "error":
                counts[stage]["errors"] += count_value
            else:
                counts[stage]["count"] += count_value

        return counts

    def close(self) -> None:
        self._db.close()

    def _prune_old_events(self) -> None:
        if self._retention_days is None or self._retention_days <= 0:
            return
        cutoff = datetime.now(UTC)
        cutoff = cutoff.replace(microsecond=0)
        cutoff_ts = cutoff.timestamp() - (self._retention_days * 24 * 3600)
        cutoff_dt = datetime.fromtimestamp(cutoff_ts, tz=UTC)
        self._db.remove(TimeQuery() < cutoff_dt)

    @contextmanager
    def _acquire_lock(self) -> Iterator[IO[str]]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            yield lock_file
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
