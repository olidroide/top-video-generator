"""Use case for triggering admin task execution."""

from __future__ import annotations

from dataclasses import dataclass

from src.shared.logging import get_logger

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

    def __init__(self) -> None:
        """Initialize use case."""

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

        return TriggerAdminTaskResult(
            queued=True,
            message=f"Task '{request.task_method}' ready for execution.",
        )
