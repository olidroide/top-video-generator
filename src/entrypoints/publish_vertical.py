"""Generate and publish daily vertical videos."""

import argparse
import asyncio
import datetime
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path

from src.adapters.vertical_video_pipeline import VerticalVideoPipelineAdapter
from src.adapters.video_publish_executor import VideoPublishExecutorAdapter
from src.application.fetch_top_videos_use_case import FetchTopVideosUseCase
from src.application.publish_vertical_use_case import (
    PublisherClientIdentity,
    PublishVerticalUseCase,
)
from src.config.settings import AppSettings, get_app_settings
from src.infrastructure.publisher_registry import build_publishers
from src.infrastructure.storage.operational_metrics_repository import OperationalMetricsRepository
from src.infrastructure.storage.publisher_state_repository import PublisherStateRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.timeseries_repository import TimeSeriesRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.execution_lock import FileExecutionLock
from src.shared.logging import get_logger, setup_logging

logger = get_logger(__name__)

_VALID_PUBLISHER_SLUGS: frozenset[str] = frozenset({"instagram", "youtube", "tiktok"})


@dataclass(frozen=True)
class VerticalPublishJobContext:
    """Dependencies and configuration for vertical publish job."""

    timeseries_repo: TimeSeriesRepository
    video_repo: VideoRepository
    release_repo: ReleaseRepository
    publishers: list
    publish_vertical_use_case: PublishVerticalUseCase
    vertical_video_pipeline: VerticalVideoPipelineAdapter
    video_publish_executor: VideoPublishExecutorAdapter
    fetch_videos_use_case: FetchTopVideosUseCase


def _build_repositories(settings: AppSettings) -> tuple[TimeSeriesRepository, VideoRepository, ReleaseRepository]:
    """Factory: build all storage repositories with correct file paths."""
    db_video_file = settings.db_video_file
    db_release_file = settings.db_release_file
    db_timeseries_file = settings.db_timeseries_file

    if not settings.is_production_env:
        db_video_file += ".test"
        db_release_file += ".test"
        db_timeseries_file += ".test"

    return (
        TimeSeriesRepository(db_timeseries_file),
        VideoRepository(Path(db_video_file)),
        ReleaseRepository(db_release_file),
    )


def _build_job_dependencies(
    timeseries_repo: TimeSeriesRepository,
    video_repo: VideoRepository,
    release_repo: ReleaseRepository,
    settings: AppSettings,
    target_platforms: set[str] | None = None,
) -> VerticalPublishJobContext:
    """Factory: build all adapters, use cases, and orchestration dependencies."""
    db_publishers_file = settings.db_release_file.replace("db_release", "db_publishers")
    if not settings.is_production_env:
        db_publishers_file += ".test"
    state_reader = PublisherStateRepository(db_publishers_file)
    publishers = build_publishers(state_reader, target_platforms=target_platforms)
    publish_vertical_use_case = PublishVerticalUseCase()
    vertical_video_pipeline = VerticalVideoPipelineAdapter(settings)
    video_publish_executor = VideoPublishExecutorAdapter()
    fetch_videos_use_case = FetchTopVideosUseCase(timeseries_repo, video_repo)

    return VerticalPublishJobContext(
        timeseries_repo=timeseries_repo,
        video_repo=video_repo,
        release_repo=release_repo,
        publishers=publishers,
        publish_vertical_use_case=publish_vertical_use_case,
        vertical_video_pipeline=vertical_video_pipeline,
        video_publish_executor=video_publish_executor,
        fetch_videos_use_case=fetch_videos_use_case,
    )


def _normalize_target_publishers(target_publishers: tuple[str, ...] | None) -> set[str] | None:
    if not target_publishers:
        return None

    normalized = {slug.strip().lower() for slug in target_publishers if slug.strip()}
    invalid = normalized - _VALID_PUBLISHER_SLUGS
    if invalid:
        invalid_text = ", ".join(sorted(invalid))
        valid_text = ", ".join(sorted(_VALID_PUBLISHER_SLUGS))
        msg = f"Invalid publisher slug(s): {invalid_text}. Valid values: {valid_text}"
        raise ValueError(msg)
    return normalized


async def main_async(*, target_publishers: tuple[str, ...] | None = None) -> None:
    target_platforms = _normalize_target_publishers(target_publishers)
    settings = get_app_settings()
    with FileExecutionLock(Path(settings.scheduler_lock_file), "vertical_publish") as execution_lock:
        if not execution_lock.acquired:
            return
        await _run_vertical_publish_job(settings, target_platforms=target_platforms)


async def _run_vertical_publish_job(settings: AppSettings, *, target_platforms: set[str] | None = None) -> None:
    metrics_db_path = (
        settings.db_timeseries_file if settings.is_production_env else f"{settings.db_timeseries_file}.test"
    )
    metrics_repo = OperationalMetricsRepository(
        metrics_db_path,
        retention_days=settings.operational_metrics_retention_days,
    )

    try:
        day = datetime.datetime.now(UTC).date()

        # Build dependencies
        timeseries_repo, video_repo, release_repo = _build_repositories(settings)
        job = _build_job_dependencies(
            timeseries_repo,
            video_repo,
            release_repo,
            settings,
            target_platforms=target_platforms,
        )

        # Build job context
        job_context = await job.publish_vertical_use_case.build_job_context(
            release_store=job.release_repo,
            publishers=job.publishers,
            fetch_top_videos_use_case=job.fetch_videos_use_case,
            day=day,
        )

        if not job_context.pending_publishers:
            logger.info("publish_vertical.no_pending_publishers", day=str(day))
            metrics_repo.record_metric_event(stage="processing", is_error=False)
            return

        # Publish pending vertical videos
        await job.publish_vertical_use_case.publish_pending_vertical_videos(
            release_store=job.release_repo,
            publish_executor=job.video_publish_executor,
            vertical_video_pipeline=job.vertical_video_pipeline,
            pending_publishers=job_context.pending_publishers,
            video_list=job_context.video_list,
            publisher_client_identity=PublisherClientIdentity(
                youtube_client_id=settings.yt_auth_user_id,
                instagram_client_id=settings.instagram_client_username,
                tiktok_client_id=settings.tiktok_user_openid,
            ),
            yt_title_template=settings.yt_title_template,
            yt_description_template=settings.yt_description_template,
        )
        metrics_repo.record_metric_event(stage="processing", is_error=False)
    except Exception:
        metrics_repo.record_metric_event(stage="processing", is_error=True)
        raise
    finally:
        metrics_repo.close()


def main(argv: list[str] | None = None) -> None:
    """Entry point for publish-vertical command."""
    parser = argparse.ArgumentParser(description="Generate and publish daily vertical videos")
    parser.add_argument(
        "--publisher",
        dest="publishers",
        action="append",
        help="Target publisher slug (instagram|youtube|tiktok). Repeat flag or use comma-separated values.",
    )
    args, _ = parser.parse_known_args(argv)

    publisher_args = args.publishers or []
    target_publishers: list[str] = []
    for value in publisher_args:
        target_publishers.extend([item.strip() for item in value.split(",") if item.strip()])

    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    asyncio.run(main_async(target_publishers=tuple(target_publishers) or None))


if __name__ == "__main__":
    main()
