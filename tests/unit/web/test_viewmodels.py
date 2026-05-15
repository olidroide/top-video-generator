"""Unit tests for web view model builders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.application.get_admin_task_status_use_case import TaskStatusResult
from src.web.viewmodels import build_admin_tasks_view_model


def _task(name: str, tasks_vm):
    return next(task for task in tasks_vm.tasks if task.name == name)


def test_build_admin_tasks_view_model_fetch_stale_after_24_hours() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=(now - timedelta(hours=25)).timestamp(),
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    fetch_task = _task("Fetch Data", tasks_vm)

    assert fetch_task.older_than_24h is True
    assert fetch_task.warning_message == "No videos fetched in 24+ hours"


def test_build_admin_tasks_view_model_daily_stale_after_24_hours() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=(now - timedelta(hours=26)).timestamp(),
        weekly_last_timestamp=None,
        latest_status_by_method={"daily": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert daily_task.older_than_24h is True
    assert daily_task.warning_message == "No daily publish in 24+ hours"


def test_build_admin_tasks_view_model_weekly_stale_after_7_days() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=(now - timedelta(days=8)).timestamp(),
        latest_status_by_method={"weekly": "success"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    weekly_task = _task("Weekly Horizontal (YouTube)", tasks_vm)

    assert weekly_task.older_than_24h is True
    assert weekly_task.warning_message == "No weekly publish in 7+ days"


def test_build_admin_tasks_view_model_non_youtube_weekly_not_applicable() -> None:
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={},
    )

    tasks_vm = build_admin_tasks_view_model(result)

    for platform_name in ("TIKTOK", "INSTAGRAM", "SPOTIFY"):
        task = _task(f"Weekly Horizontal ({platform_name})", tasks_vm)
        assert task.applicable is False
        assert task.last_run_label == "Not applicable"
