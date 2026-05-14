"""Tests for TriggerAdminTaskUseCase."""

from __future__ import annotations

import pytest

from src.application.trigger_admin_task_use_case import (
    TriggerAdminTaskRequest,
    TriggerAdminTaskUseCase,
)


class TestTriggerAdminTaskUseCase:
    """Test suite for TriggerAdminTaskUseCase."""

    @pytest.fixture
    def use_case(self) -> TriggerAdminTaskUseCase:
        """Create use case."""
        return TriggerAdminTaskUseCase()

    def test_execute_valid_fetch_method(self, use_case: TriggerAdminTaskUseCase) -> None:
        """Test execute with valid 'fetch' method."""
        request = TriggerAdminTaskRequest(task_method="fetch", user_ip="192.168.1.1")
        result = use_case.execute(request)

        assert result.queued is True
        assert "fetch" in result.message.lower()

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
