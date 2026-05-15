"""Use case for triggering admin task execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import TaskMethod, TaskRunStatus
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import TaskRunStateWriter

logger = get_logger(__name__)


@dataclass(frozen=True)
class TriggerAdminTaskRequest:
    """Request to trigger an admin background task."""

    task_method: str
    """Task identifier: 'fetch', 'daily', 'weekly'."""

    user_ip: str | None = None
    """Optional user IP for audit logging."""


@dataclass(frozen=True)
class TriggerAdminTaskResult:
    """Result of triggering an admin task."""

    queued: bool
    """True if task was successfully queued."""

    message: str
    """Status/feedback message."""


class TriggerAdminTaskUseCase:
    """
    Trigger background task execution for admin operations.

    Note: Actual task dispatch happens in web route layer via BackgroundTasks.
    This use case validates and returns feedback; route is responsible for
    scheduling execution.
    """

    def __init__(self, task_run_state_writer: TaskRunStateWriter) -> None:
        """Initialize use case with task-run persistence writer."""
        self._task_run_state_writer = task_run_state_writer

    def execute(self, request: TriggerAdminTaskRequest) -> TriggerAdminTaskResult:
        """
        Validate and return status for task trigger request.

        Args:
            request: TriggerAdminTaskRequest with task_method and optional user IP

        Returns:
            TriggerAdminTaskResult indicating if task can be queued.
        """
        valid_methods = {"fetch", "daily", "weekly"}

        if request.task_method not in valid_methods:
            logger.warning(
                "admin_task_trigger_invalid_method",
                method=request.task_method,
                user_ip=request.user_ip,
            )
            return TriggerAdminTaskResult(
                queued=False,
                message=f"Invalid task method '{request.task_method}'. Must be one of: {', '.join(valid_methods)}",
            )

        logger.info(
            "admin_task_trigger_validated",
            method=request.task_method,
            user_ip=request.user_ip,
        )

        self._task_run_state_writer.record_task_event(
            task_method=TaskMethod(request.task_method),
            status=TaskRunStatus.QUEUED,
        )

        return TriggerAdminTaskResult(
            queued=True,
            message=f"Task '{request.task_method}' scheduled. Background execution will begin shortly.",
        )

    def mark_completed(self, *, task_method: str) -> None:
        """Persist successful completion for a task method."""
        self._task_run_state_writer.record_task_event(
            task_method=TaskMethod(task_method),
            status=TaskRunStatus.SUCCESS,
        )

    def mark_failed(self, *, task_method: str, error_message: str) -> None:
        """Persist failed completion for a task method."""
        self._task_run_state_writer.record_task_event(
            task_method=TaskMethod(task_method),
            status=TaskRunStatus.FAILED,
            error_message=error_message,
        )
