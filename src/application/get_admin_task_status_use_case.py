"""Use case for fetching current admin task execution status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import TaskMethod, TaskRunStatus
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import TaskRunStateReader

logger = get_logger(__name__)


@dataclass(frozen=True)
class TaskStatusResult:
    """Result containing persisted task execution status from TinyFlux."""

    fetch_last_timestamp: float | None
    """Unix timestamp of last successful fetch, None if never."""

    daily_last_timestamp: float | None
    """Unix timestamp of last successful daily publish, None if never."""

    weekly_last_timestamp: float | None
    """Unix timestamp of last successful weekly publish, None if never."""

    latest_status_by_method: dict[str, str]
    """Latest persisted status per method (queued/success/failed)."""


class GetAdminTaskStatusUseCase:
    """
    Read current task execution status from repositories.

    Reads from TaskRunStateRepository (TinyFlux): queued/success/failed events.
    """

    def __init__(
        self,
        task_run_state_reader: TaskRunStateReader,
    ) -> None:
        """Initialize with repository ports."""
        self._task_run_state_reader = task_run_state_reader

    def execute(self) -> TaskStatusResult:
        """
        Execute status query.

        Returns:
            TaskStatusResult with fetch timestamp and release statuses by platform.
        """
        fetch_last = self._task_run_state_reader.get_latest_task_event(
            task_method=TaskMethod.FETCH,
            status=TaskRunStatus.SUCCESS,
        )
        daily_last = self._task_run_state_reader.get_latest_task_event(
            task_method=TaskMethod.DAILY,
            status=TaskRunStatus.SUCCESS,
        )
        weekly_last = self._task_run_state_reader.get_latest_task_event(
            task_method=TaskMethod.WEEKLY,
            status=TaskRunStatus.SUCCESS,
        )

        latest_status_by_method: dict[str, str] = {}
        for task_method in TaskMethod:
            latest = self._task_run_state_reader.get_latest_task_event(task_method=task_method)
            if latest is not None:
                latest_status_by_method[task_method.value] = latest.status.value

        logger.debug(
            "admin_task_status_fetched",
            fetch_last_timestamp=fetch_last.event_at.timestamp() if fetch_last else None,
            daily_last_timestamp=daily_last.event_at.timestamp() if daily_last else None,
            weekly_last_timestamp=weekly_last.event_at.timestamp() if weekly_last else None,
            methods_with_status=len(latest_status_by_method),
        )

        return TaskStatusResult(
            fetch_last_timestamp=fetch_last.event_at.timestamp() if fetch_last else None,
            daily_last_timestamp=daily_last.event_at.timestamp() if daily_last else None,
            weekly_last_timestamp=weekly_last.event_at.timestamp() if weekly_last else None,
            latest_status_by_method=latest_status_by_method,
        )
