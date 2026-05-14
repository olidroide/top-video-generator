"""Tests for GetAdminTaskStatusUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.application.get_admin_task_status_use_case import GetAdminTaskStatusUseCase
from src.domain.models import Release


class TestGetAdminTaskStatusUseCase:
    """Test suite for GetAdminTaskStatusUseCase."""

    @pytest.fixture
    def timeseries_repo_mock(self) -> MagicMock:
        """Mock TimeSeriesRepository."""
        return MagicMock(spec=["get_last_timestamp"])

    @pytest.fixture
    def release_repo_mock(self) -> MagicMock:
        """Mock ReleaseStore."""
        return MagicMock(spec=["get_release", "add_or_update_release"])

    @pytest.fixture
    def use_case(
        self,
        timeseries_repo_mock: MagicMock,
        release_repo_mock: MagicMock,
    ) -> GetAdminTaskStatusUseCase:
        """Create use case with mock repos."""
        return GetAdminTaskStatusUseCase(timeseries_repo_mock, release_repo_mock)

    def test_execute_with_all_timestamps_present(
        self,
        use_case: GetAdminTaskStatusUseCase,
        timeseries_repo_mock: MagicMock,
        release_repo_mock: MagicMock,
    ) -> None:
        """Test execute returns all timestamps when available."""
        now = datetime.now(UTC)
        fetch_time = now.replace(hour=10)
        daily_time = now.replace(hour=12)
        weekly_time = now.replace(hour=14)

        # Setup mocks
        timeseries_repo_mock.get_last_timestamp.return_value = fetch_time
        release_repo_mock.get_release.side_effect = lambda platform, client_id, release_kind: (
            Release(
                platform=platform,
                client_id=client_id,
                release_kind=release_kind,
                release_id=f"{platform}_release",
                published_at=daily_time.timestamp() if release_kind == "DAILY_VERTICAL" else weekly_time.timestamp(),
            )
            if release_kind in ["DAILY_VERTICAL", "WEEKLY_HORIZONTAL"]
            else None
        )

        # Execute
        result = use_case.execute()

        # Verify
        assert result.fetch_last_timestamp == fetch_time.timestamp()
        assert "YOUTUBE" in result.daily_releases_by_platform
        assert "YOUTUBE" in result.weekly_releases_by_platform

    def test_execute_with_no_timestamps(
        self,
        use_case: GetAdminTaskStatusUseCase,
        timeseries_repo_mock: MagicMock,
        release_repo_mock: MagicMock,
    ) -> None:
        """Test execute returns None for missing timestamps."""
        timeseries_repo_mock.get_last_timestamp.return_value = None
        release_repo_mock.get_release.return_value = None

        result = use_case.execute()

        assert result.fetch_last_timestamp is None
        assert result.daily_releases_by_platform == {}
        assert result.weekly_releases_by_platform == {}

    def test_execute_partial_releases(
        self,
        use_case: GetAdminTaskStatusUseCase,
        timeseries_repo_mock: MagicMock,
        release_repo_mock: MagicMock,
    ) -> None:
        """Test execute handles partial release data."""
        now = datetime.now(UTC)
        fetch_time = now

        timeseries_repo_mock.get_last_timestamp.return_value = fetch_time

        def get_release_side_effect(platform: str, client_id: str, release_kind: str) -> Release | None:
            if platform == "YOUTUBE" and release_kind == "DAILY_VERTICAL":
                return Release(
                    platform=platform,
                    client_id=client_id,
                    release_kind=release_kind,
                    release_id="yt_daily",
                    published_at=now.timestamp(),
                )
            return None

        release_repo_mock.get_release.side_effect = get_release_side_effect

        result = use_case.execute()

        assert result.fetch_last_timestamp == fetch_time.timestamp()
        assert "YOUTUBE" in result.daily_releases_by_platform
        assert len(result.daily_releases_by_platform) == 1
        assert result.weekly_releases_by_platform == {}
