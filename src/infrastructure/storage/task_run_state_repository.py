"""Task run state repository backed by TinyFlux."""

from __future__ import annotations

import fcntl
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Iterator

from tinyflux import Point, TagQuery, TinyFlux

from src.domain.models import TaskMethod, TaskRunState, TaskRunStatus


class TaskRunStateRepository:
    """Persist and query admin task execution events in TinyFlux."""

    _MEASUREMENT = "Task run state"

    def __init__(self, db_path: str) -> None:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyFlux(db_path)
        self._lock_path = db_file.with_suffix(f"{db_file.suffix}.lock")

    def record_task_event(
        self,
        *,
        task_method: TaskMethod,
        status: TaskRunStatus,
        error_message: str | None = None,
        event_time: datetime | None = None,
    ) -> None:
        point_time = (event_time or datetime.now(UTC)).astimezone(UTC)
        with self._acquire_lock():
            self._db.insert(
                Point(
                    measurement=self._MEASUREMENT,
                    time=point_time,
                    tags={
                        "task_method": task_method.value,
                        "status": status.value,
                        "error_message": error_message or "",
                    },
                    fields={"count": 1},
                )
            )

    def get_latest_task_event(
        self,
        *,
        task_method: TaskMethod,
        status: TaskRunStatus | None = None,
    ) -> TaskRunState | None:
        query = TagQuery().task_method == task_method.value
        if status is not None:
            query = query & (TagQuery().status == status.value)

        with self._acquire_lock():
            points = self._db.search(query)

        filtered = [point for point in points if point.measurement == self._MEASUREMENT and point.time is not None]
        if not filtered:
            return None

        latest = max(filtered, key=lambda point: cast("datetime", point.time))
        return TaskRunState(
            task_method=TaskMethod(latest.tags.get("task_method") or task_method.value),
            status=TaskRunStatus(latest.tags.get("status") or TaskRunStatus.QUEUED.value),
            event_at=cast("datetime", latest.time).astimezone(UTC),
            error_message=(latest.tags.get("error_message") or None),
        )

    def close(self) -> None:
        self._db.close()

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
