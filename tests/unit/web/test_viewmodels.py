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

    for platform_name in ("TIKTOK", "INSTAGRAM"):
        task = _task(f"Weekly Horizontal ({platform_name})", tasks_vm)
        assert task.applicable is False
        assert task.last_run_label == "Not applicable"


def test_build_admin_tasks_view_model_daily_failed_recommends_retry_and_shows_details() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"daily": "failed"},
        latest_error_by_method={"daily": "challenge_required"},
        daily_publish_timestamps_by_platform={
            "YOUTUBE": (now - timedelta(hours=2)).timestamp(),
            "INSTAGRAM": (now - timedelta(hours=26)).timestamp(),
        },
        latest_video_artifact_path="videos/20260515/20260515_vertical_format.mp4",
        latest_video_artifact_timestamp=(now - timedelta(hours=1)).timestamp(),
    )

    tasks_vm = build_admin_tasks_view_model(result)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert daily_task.action_label == "Retry Daily"
    assert daily_task.warning_message == "Last daily run failed. Retry recommended."
    assert daily_task.last_error == "challenge_required"
    assert daily_task.source == "videos_folder"
    assert any(row.startswith("Last processed video:") for row in daily_task.detail_rows)
    assert any("Artifact path: videos/20260515/20260515_vertical_format.mp4" in row for row in daily_task.detail_rows)
    assert any(row.startswith("YOUTUBE:") for row in daily_task.detail_rows)
    assert any(row.startswith("INSTAGRAM:") for row in daily_task.detail_rows)
    assert any(row == "TIKTOK: Never" for row in daily_task.detail_rows)


def test_build_admin_tasks_view_model_running_methods_shows_is_running() -> None:
    result = TaskStatusResult(
        fetch_last_timestamp=None,
        daily_last_timestamp=None,
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "queued"},
        running_methods={"fetch"},
    )

    tasks_vm = build_admin_tasks_view_model(result)
    fetch_task = _task("Fetch Data", tasks_vm)
    daily_task = _task("Daily Vertical Videos", tasks_vm)

    assert fetch_task.is_running is True
    assert daily_task.is_running is False
    assert tasks_vm.any_running is True


def test_build_admin_tasks_view_model_no_running_tasks() -> None:
    now = datetime.now(UTC)
    result = TaskStatusResult(
        fetch_last_timestamp=now.timestamp(),
        daily_last_timestamp=now.timestamp(),
        weekly_last_timestamp=None,
        latest_status_by_method={"fetch": "success", "daily": "success"},
        running_methods=set(),
    )

    tasks_vm = build_admin_tasks_view_model(result)

    assert tasks_vm.any_running is False
    for task in tasks_vm.tasks:
        assert task.is_running is False
