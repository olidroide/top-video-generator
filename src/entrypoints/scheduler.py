"""Persistent in-container scheduler for the main publish jobs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.config.settings import AppSettings, get_app_settings
from src.entrypoints.fetch_data import main_async as fetch_data_main_async
from src.entrypoints.publish_vertical import main_async as publish_vertical_main_async
from src.entrypoints.publish_video import main_async as publish_weekly_main_async
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)

JobRunner = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class ScheduledJob:
    name: str
    hour: int
    minute: int
    runner: JobRunner
    day_of_week: int | None = None


def _resolve_scheduler_timezone(settings: AppSettings) -> tzinfo:
    if settings.scheduler_timezone:
        try:
            return ZoneInfo(settings.scheduler_timezone)
        except ZoneInfoNotFoundError as exc:
            msg = f"Unknown scheduler timezone: {settings.scheduler_timezone}"
            raise ValueError(msg) from exc

    local_timezone = datetime.now().astimezone().tzinfo
    if local_timezone is None:
        return UTC
    return local_timezone


def _job_is_due(job: ScheduledJob, now: datetime) -> bool:
    if job.day_of_week is not None and now.weekday() != job.day_of_week:
        return False
    scheduled_at = now.replace(hour=job.hour, minute=job.minute, second=0, microsecond=0)
    return now >= scheduled_at


def _job_run_key(job: ScheduledJob, now: datetime) -> str:
    if job.day_of_week is not None:
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return now.date().isoformat()


def _build_jobs(settings: AppSettings) -> list[ScheduledJob]:
    return [
        ScheduledJob(
            name="fetch_data",
            hour=settings.scheduler_fetch_hour,
            minute=settings.scheduler_fetch_minute,
            runner=fetch_data_main_async,
        ),
        ScheduledJob(
            name="vertical_publish",
            hour=settings.scheduler_vertical_publish_hour,
            minute=settings.scheduler_vertical_publish_minute,
            runner=publish_vertical_main_async,
        ),
        ScheduledJob(
            name="weekly_publish",
            hour=settings.scheduler_weekly_publish_hour,
            minute=settings.scheduler_weekly_publish_minute,
            runner=publish_weekly_main_async,
            day_of_week=settings.scheduler_weekly_publish_day_of_week,
        ),
    ]


async def _write_heartbeat(
    heartbeat_file: Path,
    *,
    status: str,
    last_job_name: str | None,
    last_successful_job_name: str | None,
    error: str | None = None,
) -> None:
    payload: dict[str, str | None] = {
        "status": status,
        "updated_at": datetime.now(UTC).isoformat(),
        "last_job": last_job_name,
        "last_successful_job": last_successful_job_name,
        "error": error,
    }
    await asyncio.to_thread(_write_heartbeat_sync, heartbeat_file, payload)


def _write_heartbeat_sync(heartbeat_file: Path, payload: dict[str, str | None]) -> None:
    heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
    heartbeat_file.write_text(json.dumps(payload), encoding="utf-8")


def heartbeat_is_fresh(heartbeat_file: Path, stale_seconds: int, now: datetime | None = None) -> bool:
    if not heartbeat_file.exists():
        return False
    heartbeat_raw = heartbeat_file.read_text(encoding="utf-8")
    heartbeat = json.loads(heartbeat_raw)
    updated_at_raw = heartbeat.get("updated_at")
    if not updated_at_raw:
        return False
    now = now or datetime.now(UTC)
    updated_at = datetime.fromisoformat(updated_at_raw)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=UTC)
    return (now.astimezone(UTC) - updated_at.astimezone(UTC)).total_seconds() <= stale_seconds


async def main_async() -> None:
    settings = get_app_settings()
    heartbeat_file = Path(settings.scheduler_heartbeat_file)
    scheduler_timezone = _resolve_scheduler_timezone(settings)
    jobs = _build_jobs(settings)
    last_run_keys: dict[str, str] = {}
    last_successful_job_name: str | None = None

    logger.info(
        "scheduler.started",
        timezone=str(scheduler_timezone),
        poll_interval_seconds=settings.scheduler_poll_interval_seconds,
    )

    while True:
        now = datetime.now(scheduler_timezone)
        await _write_heartbeat(
            heartbeat_file,
            status="idle",
            last_job_name=None,
            last_successful_job_name=last_successful_job_name,
        )
        for job in jobs:
            if not _job_is_due(job, now):
                continue
            run_key = _job_run_key(job, now)
            if last_run_keys.get(job.name) == run_key:
                continue

            last_run_keys[job.name] = run_key
            logger.info("scheduler.job_started", job=job.name, scheduled_date=str(now.date()))
            await _write_heartbeat(
                heartbeat_file,
                status="running",
                last_job_name=job.name,
                last_successful_job_name=last_successful_job_name,
            )
            try:
                await job.runner()
                last_successful_job_name = job.name
                logger.info("scheduler.job_finished", job=job.name)
                await _write_heartbeat(
                    heartbeat_file,
                    status="idle",
                    last_job_name=job.name,
                    last_successful_job_name=last_successful_job_name,
                )
            except Exception as exc:
                logger.exception("scheduler.job_failed", job=job.name, error=str(exc))
                await _write_heartbeat(
                    heartbeat_file,
                    status="idle",
                    last_job_name=job.name,
                    last_successful_job_name=last_successful_job_name,
                    error=f"{job.name} failed: {exc!s}",
                )
                # Do NOT raise: allow other jobs in cycle to continue

        await asyncio.sleep(settings.scheduler_poll_interval_seconds)


def main() -> None:
    """Entry point for scheduler command."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
