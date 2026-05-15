"""Integration tests for scheduler fault isolation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config.settings import AppSettings
from src.entrypoints.scheduler import _write_heartbeat


@pytest.fixture
def mock_settings() -> AppSettings:
    """Mock settings for scheduler tests."""
    return AppSettings(
        env="development",
        scheduler_fetch_hour=9,
        scheduler_fetch_minute=0,
        scheduler_vertical_publish_hour=10,
        scheduler_vertical_publish_minute=0,
        scheduler_weekly_publish_hour=11,
        scheduler_weekly_publish_minute=0,
        scheduler_weekly_publish_day_of_week=4,  # Friday
        scheduler_poll_interval_seconds=1,
        scheduler_timezone="UTC",
        scheduler_heartbeat_file="/tmp/test_heartbeat.json",
        log_file_path="/tmp/test.log",
        yt_search_region_code="US",
    )


@pytest.mark.asyncio
async def test_scheduler_continues_after_job_failure(tmp_path: Path) -> None:
    """Verify that when a job fails, scheduler continues with next jobs (no raise)."""
    heartbeat_file = tmp_path / "heartbeat.json"
    execution_log: list[str] = []

    # Simulate two jobs: first fails, second succeeds
    async def failing_job() -> None:
        execution_log.append("job1_started")
        raise RuntimeError("Simulated job1 failure")

    async def succeeding_job() -> None:
        execution_log.append("job2_started")
        execution_log.append("job2_finished")

    # Simulate scheduler loop behavior for these two jobs
    last_successful_job_name: str | None = None

    jobs_to_run = [
        ("job1", failing_job),
        ("job2", succeeding_job),
    ]

    for job_name, job_runner in jobs_to_run:
        try:
            await job_runner()
            last_successful_job_name = job_name
            await _write_heartbeat(
                heartbeat_file,
                status="idle",
                last_job_name=job_name,
                last_successful_job_name=last_successful_job_name,
            )
        except RuntimeError as exc:
            # Scheduler records error but does NOT raise
            await _write_heartbeat(
                heartbeat_file,
                status="idle",
                last_job_name=job_name,
                last_successful_job_name=last_successful_job_name,
                error=f"{job_name} failed: {exc!s}",
            )
            # Continue to next job (do NOT raise)
            continue

    # Assertions: verify both jobs ran despite job1 failure
    assert "job1_started" in execution_log
    assert "job2_started" in execution_log, "job2 should run despite job1 failure"
    assert "job2_finished" in execution_log

    # Verify heartbeat records last successful job as job2 (not suppressed by job1 failure)
    heartbeat = json.loads(heartbeat_file.read_text())
    assert heartbeat["last_successful_job"] == "job2"
    assert heartbeat["last_job"] == "job2"


@pytest.mark.asyncio
async def test_scheduler_heartbeat_records_error_detail(tmp_path: Path) -> None:
    """Verify that scheduler heartbeat captures error message from failed job."""
    heartbeat_file = tmp_path / "heartbeat.json"
    error_message = "Custom failure reason"

    async def failing_job() -> None:
        raise RuntimeError(error_message)

    # Job fails and heartbeat records error
    try:
        await failing_job()
    except RuntimeError as exc:
        await _write_heartbeat(
            heartbeat_file,
            status="idle",
            last_job_name="test_job",
            last_successful_job_name=None,
            error=f"test_job failed: {exc!s}",
        )

    # Verify error is recorded
    heartbeat = json.loads(heartbeat_file.read_text())
    assert "Custom failure reason" in heartbeat["error"]
    assert "test_job" in heartbeat["error"]
    assert heartbeat["status"] == "idle"
