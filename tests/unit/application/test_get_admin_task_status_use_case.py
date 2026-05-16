"""Tests for GetAdminTaskStatusUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.application.get_admin_task_status_use_case import GetAdminTaskStatusUseCase
from src.domain.models import TaskMethod, TaskRunState, TaskRunStatus


class TestGetAdminTaskStatusUseCase:
    """Test suite for GetAdminTaskStatusUseCase."""

    @pytest.fixture
    def task_run_state_reader_mock(self) -> MagicMock:
        return MagicMock(spec=["get_latest_task_event"])

    @pytest.fixture
    def release_store_mock(self) -> MagicMock:
        return MagicMock(spec=["get_latest_release"])

    @pytest.fixture
    def use_case(
        self,
        task_run_state_reader_mock: MagicMock,
        release_store_mock: MagicMock,
        tmp_path: Path,
    ) -> GetAdminTaskStatusUseCase:
        return GetAdminTaskStatusUseCase(
            task_run_state_reader_mock,
            release_store=release_store_mock,
            video_generated_folder=str(tmp_path),
        )

    def test_execute_with_all_success_timestamps(
        self,
        use_case: GetAdminTaskStatusUseCase,
        task_run_state_reader_mock: MagicMock,
        release_store_mock: MagicMock,
    ) -> None:
        now = datetime.now(UTC)

        latest_map: dict[tuple[TaskMethod, TaskRunStatus | None], TaskRunState | None] = {
            (TaskMethod.FETCH, TaskRunStatus.SUCCESS): TaskRunState(
                task_method=TaskMethod.FETCH,
                status=TaskRunStatus.SUCCESS,
                event_at=now,
            ),
            (TaskMethod.DAILY, TaskRunStatus.SUCCESS): TaskRunState(
                task_method=TaskMethod.DAILY,
                status=TaskRunStatus.SUCCESS,
                event_at=now,
            ),
            (TaskMethod.WEEKLY, TaskRunStatus.SUCCESS): TaskRunState(
                task_method=TaskMethod.WEEKLY,
                status=TaskRunStatus.SUCCESS,
                event_at=now,
            ),
            (TaskMethod.FETCH, None): TaskRunState(
                task_method=TaskMethod.FETCH,
                status=TaskRunStatus.SUCCESS,
                event_at=now,
            ),
            (TaskMethod.DAILY, None): TaskRunState(
                task_method=TaskMethod.DAILY,
                status=TaskRunStatus.QUEUED,
                event_at=now,
            ),
            (TaskMethod.WEEKLY, None): TaskRunState(
                task_method=TaskMethod.WEEKLY,
                status=TaskRunStatus.FAILED,
                event_at=now,
                error_message="boom",
            ),
            (TaskMethod.FETCH, TaskRunStatus.QUEUED): None,
            (TaskMethod.DAILY, TaskRunStatus.QUEUED): TaskRunState(
                task_method=TaskMethod.DAILY,
                status=TaskRunStatus.QUEUED,
                event_at=now,
            ),
            (TaskMethod.WEEKLY, TaskRunStatus.QUEUED): None,
        }

        def _side_effect(*, task_method: TaskMethod, status: TaskRunStatus | None = None):
            return latest_map[(task_method, status)]

        task_run_state_reader_mock.get_latest_task_event.side_effect = _side_effect
        release_store_mock.get_latest_release.return_value = None

        result = use_case.execute()

        assert result.fetch_last_timestamp == now.timestamp()
        assert result.daily_last_timestamp == now.timestamp()
        assert result.weekly_last_timestamp == now.timestamp()
        assert result.latest_status_by_method == {
            "fetch": "success",
            "daily": "queued",
            "weekly": "failed",
        }
        assert result.latest_error_by_method == {"weekly": "boom"}
        assert result.daily_publish_timestamps_by_platform == {}

    def test_execute_with_no_events(
        self,
        use_case: GetAdminTaskStatusUseCase,
        task_run_state_reader_mock: MagicMock,
        release_store_mock: MagicMock,
    ) -> None:
        task_run_state_reader_mock.get_latest_task_event.return_value = None
        release_store_mock.get_latest_release.return_value = None

        result = use_case.execute()

        assert result.fetch_last_timestamp is None
        assert result.daily_last_timestamp is None
        assert result.weekly_last_timestamp is None
        assert result.latest_status_by_method == {}

    def test_execute_reports_latest_video_artifact_and_platform_releases(
        self,
        task_run_state_reader_mock: MagicMock,
        release_store_mock: MagicMock,
        tmp_path: Path,
    ) -> None:
        task_run_state_reader_mock.get_latest_task_event.return_value = None

        now = datetime.now(UTC).timestamp()
        release_store_mock.get_latest_release.side_effect = [
            MagicMock(published_at=now),
            None,
            None,
            None,
        ]

        video_dir = tmp_path / "20260515"
        video_dir.mkdir(parents=True)
        artifact = video_dir / "20260515_vertical_format.mp4"
        artifact.write_bytes(b"mp4")

        use_case = GetAdminTaskStatusUseCase(
            task_run_state_reader_mock,
            release_store=release_store_mock,
            video_generated_folder=str(tmp_path),
        )

        result = use_case.execute()

        assert result.daily_publish_timestamps_by_platform.get("YOUTUBE") == now
        assert result.latest_video_artifact_path is not None
        assert result.latest_video_artifact_path.endswith("20260515_vertical_format.mp4")
        assert result.latest_video_artifact_timestamp is not None

    def test_running_methods_includes_recent_queued_only(
        self,
        use_case: GetAdminTaskStatusUseCase,
        task_run_state_reader_mock: MagicMock,
        release_store_mock: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        from datetime import timedelta

        recent_queued = TaskRunState(
            task_method=TaskMethod.FETCH,
            status=TaskRunStatus.QUEUED,
            event_at=now - timedelta(seconds=60),
        )
        stale_queued = TaskRunState(
            task_method=TaskMethod.DAILY,
            status=TaskRunStatus.QUEUED,
            event_at=now - timedelta(minutes=10),
        )
        success_weekly = TaskRunState(
            task_method=TaskMethod.WEEKLY,
            status=TaskRunStatus.SUCCESS,
            event_at=now - timedelta(hours=1),
        )

        def _side_effect(*, task_method: TaskMethod, status: TaskRunStatus | None = None):
            if status is TaskRunStatus.QUEUED:
                if task_method == TaskMethod.FETCH:
                    return recent_queued
                if task_method == TaskMethod.DAILY:
                    return stale_queued
                return None
            if task_method == TaskMethod.WEEKLY:
                return success_weekly
            return None

        task_run_state_reader_mock.get_latest_task_event.side_effect = _side_effect
        release_store_mock.get_latest_release.return_value = None

        result = use_case.execute()

        assert "fetch" in result.running_methods
        assert "daily" not in result.running_methods
        assert "weekly" not in result.running_methods

    def test_get_task_started_at_returns_queued_timestamp(
        self,
        use_case: GetAdminTaskStatusUseCase,
        task_run_state_reader_mock: MagicMock,
    ) -> None:
        now = datetime.now(UTC)
        from datetime import timedelta

        queued_event = TaskRunState(
            task_method=TaskMethod.FETCH,
            status=TaskRunStatus.QUEUED,
            event_at=now - timedelta(seconds=30),
        )
        success_event = TaskRunState(
            task_method=TaskMethod.FETCH,
            status=TaskRunStatus.SUCCESS,
            event_at=now,
        )

        def _side_effect(*, task_method: TaskMethod, status: TaskRunStatus | None = None):
            if status is TaskRunStatus.QUEUED:
                return queued_event
            return success_event

        task_run_state_reader_mock.get_latest_task_event.side_effect = _side_effect

        result = use_case.get_task_started_at("fetch")

        assert result is not None
        assert result == pytest.approx(queued_event.event_at.timestamp(), abs=1)

    def test_get_task_started_at_returns_none_for_invalid_method(
        self,
        use_case: GetAdminTaskStatusUseCase,
    ) -> None:
        assert use_case.get_task_started_at("invalid") is None

    def test_get_task_started_at_returns_none_when_no_queued_event(
        self,
        use_case: GetAdminTaskStatusUseCase,
        task_run_state_reader_mock: MagicMock,
    ) -> None:
        task_run_state_reader_mock.get_latest_task_event.return_value = None

        assert use_case.get_task_started_at("fetch") is None
