from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.domain.models import TaskMethod, TaskRunStatus
from src.infrastructure.storage.task_run_state_repository import TaskRunStateRepository


def test_record_and_read_latest_task_event(tmp_path) -> None:
    db_path = tmp_path / "timeseries.csv"
    repo = TaskRunStateRepository(str(db_path))

    now = datetime.now(UTC)
    repo.record_task_event(
        task_method=TaskMethod.FETCH,
        status=TaskRunStatus.QUEUED,
        event_time=now - timedelta(minutes=2),
    )
    repo.record_task_event(
        task_method=TaskMethod.FETCH,
        status=TaskRunStatus.SUCCESS,
        event_time=now - timedelta(minutes=1),
    )

    latest = repo.get_latest_task_event(task_method=TaskMethod.FETCH)
    assert latest is not None
    assert latest.status == TaskRunStatus.SUCCESS

    latest_success = repo.get_latest_task_event(task_method=TaskMethod.FETCH, status=TaskRunStatus.SUCCESS)
    assert latest_success is not None
    assert latest_success.status == TaskRunStatus.SUCCESS

    repo.close()


def test_latest_task_event_returns_none_when_absent(tmp_path) -> None:
    repo = TaskRunStateRepository(str(tmp_path / "timeseries.csv"))

    latest = repo.get_latest_task_event(task_method=TaskMethod.WEEKLY)

    assert latest is None
    repo.close()


def test_record_task_event_persists_error_message(tmp_path) -> None:
    repo = TaskRunStateRepository(str(tmp_path / "timeseries.csv"))

    repo.record_task_event(
        task_method=TaskMethod.DAILY,
        status=TaskRunStatus.FAILED,
        error_message="upload failed",
        event_time=datetime.now(UTC),
    )

    latest = repo.get_latest_task_event(task_method=TaskMethod.DAILY)

    assert latest is not None
    assert latest.status == TaskRunStatus.FAILED
    assert latest.error_message == "upload failed"
    repo.close()
