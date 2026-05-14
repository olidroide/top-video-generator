"""Use case for fetching current admin task execution status."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import ReleaseStore, TimeSeriesReader

logger = get_logger(__name__)


@dataclass(frozen=True)
class TaskStatusResult:
    """Result containing current task execution status from repositories."""

    fetch_last_timestamp: float | None
    """Unix timestamp of last fetch (from timeseries), None if never."""

    daily_releases_by_platform: dict[str, float]
    """Platform -> last daily release timestamp. Empty dict if no releases recorded."""

    weekly_releases_by_platform: dict[str, float]
    """Platform -> last weekly release timestamp. Empty dict if no releases recorded."""


class GetAdminTaskStatusUseCase:
    """
    Read current task execution status from repositories.

    Reads from:
    - TimeSeriesRepository: last_timestamp (fetch operation)
    - ReleaseRepository: daily & weekly releases by platform
    """

    def __init__(
        self,
        timeseries_repo: TimeSeriesReader,
        release_repo: ReleaseStore,
    ) -> None:
        """Initialize with repository ports."""
        self._timeseries_repo = timeseries_repo
        self._release_repo = release_repo

    def execute(self) -> TaskStatusResult:
        """
        Execute status query.

        Returns:
            TaskStatusResult with fetch timestamp and release statuses by platform.
        """
        # Fetch last timeseries timestamp
        fetch_last = self._timeseries_repo.get_last_timestamp()
        fetch_last_float = fetch_last.timestamp() if fetch_last else None

        # Query daily releases (DAILY_VERTICAL) for each platform
        daily_releases = {}
        for platform in ["YOUTUBE", "TIKTOK", "INSTAGRAM", "SPOTIFY"]:
            release = self._release_repo.get_release(
                platform=platform,
                client_id="default",
                release_kind="DAILY_VERTICAL",
            )
            if release and release.published_at:
                daily_releases[platform] = release.published_at

        # Query weekly releases (WEEKLY_HORIZONTAL) for each platform
        weekly_releases = {}
        for platform in ["YOUTUBE", "TIKTOK", "INSTAGRAM", "SPOTIFY"]:
            release = self._release_repo.get_release(
                platform=platform,
                client_id="default",
                release_kind="WEEKLY_HORIZONTAL",
            )
            if release and release.published_at:
                weekly_releases[platform] = release.published_at

        logger.debug(
            "admin_task_status_fetched",
            fetch_last_timestamp=fetch_last_float,
            daily_platforms=len(daily_releases),
            weekly_platforms=len(weekly_releases),
        )

        return TaskStatusResult(
            fetch_last_timestamp=fetch_last_float,
            daily_releases_by_platform=daily_releases,
            weekly_releases_by_platform=weekly_releases,
        )
