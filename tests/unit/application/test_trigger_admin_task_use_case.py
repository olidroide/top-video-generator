"""Tests for TriggerAdminTaskUseCase."""

from __future__ import annotations

import pytest

from src.application.trigger_admin_task_use_case import (
    TriggerAdminTaskRequest,
    TriggerAdminTaskUseCase,
)
from src.domain.models import TaskMethod, TaskRunStatus


class TestTriggerAdminTaskUseCase:
    """Test suite for TriggerAdminTaskUseCase."""

    @pytest.fixture
    def writer_mock(self):
        from unittest.mock import MagicMock

        return MagicMock(spec=["record_task_event"])

    @pytest.fixture
    def use_case(self, writer_mock) -> TriggerAdminTaskUseCase:
        """Create use case."""
        return TriggerAdminTaskUseCase(writer_mock)

    def test_execute_valid_fetch_method(self, use_case: TriggerAdminTaskUseCase, writer_mock) -> None:
        """Test execute with valid 'fetch' method."""
        request = TriggerAdminTaskRequest(task_method="fetch", user_ip="192.168.1.1")
        result = use_case.execute(request)

        assert result.queued is True
        assert "fetch" in result.message.lower()
        writer_mock.record_task_event.assert_called_once_with(
            task_method=TaskMethod.FETCH,
            status=TaskRunStatus.QUEUED,
        )

    def test_execute_valid_daily_method(self, use_case: TriggerAdminTaskUseCase) -> None:
        """Test execute with valid 'daily' method."""
        request = TriggerAdminTaskRequest(task_method="daily")
        result = use_case.execute(request)

        assert result.queued is True
        assert "daily" in result.message.lower()

    def test_execute_valid_weekly_method(self, use_case: TriggerAdminTaskUseCase) -> None:
        """Test execute with valid 'weekly' method."""
        request = TriggerAdminTaskRequest(task_method="weekly")
        result = use_case.execute(request)

        assert result.queued is True
        assert "weekly" in result.message.lower()

    def test_execute_invalid_method(self, use_case: TriggerAdminTaskUseCase) -> None:
        """Test execute rejects invalid method."""
        request = TriggerAdminTaskRequest(task_method="invalid", user_ip="192.168.1.1")
        result = use_case.execute(request)

        assert result.queued is False
        assert "invalid" in result.message.lower()

    def test_execute_without_user_ip(self, use_case: TriggerAdminTaskUseCase) -> None:
        """Test execute works without user IP."""
        request = TriggerAdminTaskRequest(task_method="fetch")
        result = use_case.execute(request)

        assert result.queued is True

    def test_mark_completed_records_success(self, use_case: TriggerAdminTaskUseCase, writer_mock) -> None:
        use_case.mark_completed(task_method="daily")

        writer_mock.record_task_event.assert_called_once_with(
            task_method=TaskMethod.DAILY,
            status=TaskRunStatus.SUCCESS,
        )

    def test_mark_failed_records_failure(self, use_case: TriggerAdminTaskUseCase, writer_mock) -> None:
        use_case.mark_failed(task_method="weekly", error_message="boom")

        writer_mock.record_task_event.assert_called_once_with(
            task_method=TaskMethod.WEEKLY,
            status=TaskRunStatus.FAILED,
            error_message="boom",
        )
