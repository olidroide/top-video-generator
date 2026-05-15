"""Use case for fetching current admin task execution status."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from src.domain.models import Platform, ReleaseKind, TaskMethod, TaskRunStatus
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import ReleaseStore, TaskRunStateReader

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

    latest_status_by_method: dict[str, str] = field(default_factory=dict)
    """Latest persisted status per method (queued/success/failed)."""

    latest_error_by_method: dict[str, str] = field(default_factory=dict)
    """Latest persisted error message per method, when available."""

    daily_publish_timestamps_by_platform: dict[str, float] = field(default_factory=dict)
    """Latest daily vertical publish timestamp per platform (unix seconds)."""

    latest_video_artifact_path: str | None = None
    """Most recent generated mp4 artifact path under videos folder, if any."""

    latest_video_artifact_timestamp: float | None = None
    """Filesystem mtime (unix seconds) for latest generated mp4 artifact, if any."""


class GetAdminTaskStatusUseCase:
    """
    Read current task execution status from repositories.

    Reads from TaskRunStateRepository (TinyFlux): queued/success/failed events.
    """

    def __init__(
        self,
        task_run_state_reader: TaskRunStateReader,
        release_store: ReleaseStore,
        video_generated_folder: str,
    ) -> None:
        """Initialize with repository ports."""
        self._task_run_state_reader = task_run_state_reader
        self._release_store = release_store
        self._video_generated_folder = video_generated_folder

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
        latest_error_by_method: dict[str, str] = {}
        for task_method in TaskMethod:
            latest = self._task_run_state_reader.get_latest_task_event(task_method=task_method)
            if latest is not None:
                latest_status_by_method[task_method.value] = latest.status.value
                if latest.error_message:
                    latest_error_by_method[task_method.value] = latest.error_message

        daily_publish_timestamps_by_platform: dict[str, float] = {}
        for platform in (Platform.YOUTUBE, Platform.TIKTOK, Platform.INSTAGRAM, Platform.SPOTIFY):
            latest_release = self._release_store.get_latest_release(
                platform=platform.value,
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
            )
            if latest_release is None or latest_release.published_at is None:
                continue
            daily_publish_timestamps_by_platform[platform.value] = latest_release.published_at

        latest_artifact_path, latest_artifact_timestamp = self._resolve_latest_video_artifact()

        logger.debug(
            "admin_task_status_fetched",
            fetch_last_timestamp=fetch_last.event_at.timestamp() if fetch_last else None,
            daily_last_timestamp=daily_last.event_at.timestamp() if daily_last else None,
            weekly_last_timestamp=weekly_last.event_at.timestamp() if weekly_last else None,
            methods_with_status=len(latest_status_by_method),
            methods_with_errors=len(latest_error_by_method),
            daily_publish_platforms=len(daily_publish_timestamps_by_platform),
            latest_video_artifact_path=latest_artifact_path,
        )

        return TaskStatusResult(
            fetch_last_timestamp=fetch_last.event_at.timestamp() if fetch_last else None,
            daily_last_timestamp=daily_last.event_at.timestamp() if daily_last else None,
            weekly_last_timestamp=weekly_last.event_at.timestamp() if weekly_last else None,
            latest_status_by_method=latest_status_by_method,
            latest_error_by_method=latest_error_by_method,
            daily_publish_timestamps_by_platform=daily_publish_timestamps_by_platform,
            latest_video_artifact_path=latest_artifact_path,
            latest_video_artifact_timestamp=latest_artifact_timestamp,
        )

    def _resolve_latest_video_artifact(self) -> tuple[str | None, float | None]:
        root = Path(self._video_generated_folder)
        if not root.exists() or not root.is_dir():
            return None, None

        date_dirs = [path for path in root.iterdir() if path.is_dir() and re.fullmatch(r"\d{8}", path.name)]
        if date_dirs:
            # Folder names are YYYYMMDD, so lexical max is latest day.
            target_dir = max(date_dirs, key=lambda path: path.name)
            latest_in_dir = self._latest_mp4_in_tree(target_dir)
            if latest_in_dir is not None:
                return str(latest_in_dir), latest_in_dir.stat().st_mtime

        latest_any = self._latest_mp4_in_tree(root)
        if latest_any is None:
            return None, None
        return str(latest_any), latest_any.stat().st_mtime

    @staticmethod
    def _latest_mp4_in_tree(root: Path) -> Path | None:
        candidates: list[Path] = [path for path in root.rglob("*.mp4") if path.is_file()]
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)
