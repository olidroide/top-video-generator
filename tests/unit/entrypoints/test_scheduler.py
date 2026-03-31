from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from src.entrypoints.scheduler import ScheduledJob, _heartbeat_is_fresh, _job_is_due, _job_run_key


async def _noop() -> None:
    return None


def test_job_is_due_only_after_scheduled_time() -> None:
    job = ScheduledJob(name="fetch_data", hour=15, minute=0, runner=_noop)

    assert not _job_is_due(job, datetime(2026, 3, 31, 14, 59, tzinfo=UTC))
    assert _job_is_due(job, datetime(2026, 3, 31, 15, 0, tzinfo=UTC))


def test_weekly_job_run_key_uses_iso_week() -> None:
    now = datetime(2026, 3, 28, 17, 0, tzinfo=UTC)
    iso_year, iso_week, _ = now.isocalendar()
    job = ScheduledJob(name="weekly_publish", hour=17, minute=0, runner=_noop, day_of_week=5)

    assert _job_run_key(job, now) == f"{iso_year}-W{iso_week:02d}"


def test_heartbeat_is_fresh_checks_timestamp_window(tmp_path) -> None:
    heartbeat_file = tmp_path / "scheduler-heartbeat.json"
    now = datetime(2026, 3, 31, 12, 0, tzinfo=UTC)
    heartbeat_file.write_text(
        json.dumps({"updated_at": (now - timedelta(seconds=30)).isoformat()}),
        encoding="utf-8",
    )

    assert _heartbeat_is_fresh(heartbeat_file, stale_seconds=60, now=now)
    assert not _heartbeat_is_fresh(heartbeat_file, stale_seconds=10, now=now)
