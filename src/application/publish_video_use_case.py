from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.domain.models import CanonicalVideo, Platform, PublishingResult, Release, ReleaseKind, TimeseriesRange
from src.domain.services.scoring_service import rank_videos_by_score
from src.domain.services.video_metadata_service import generate_youtube_description, generate_youtube_title
from src.domain.utils import extract_video_hashtags
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import HorizontalVideoPipeline, ReleaseStore, VideoPublisher, WeeklyYouTubeUploader

logger = get_logger(__name__)


@dataclass(frozen=True)
class PublishVideoRequest:
    video_list: tuple[CanonicalVideo, ...]
    file_path: str
    title: str
    description: str


@dataclass(frozen=True)
class PublishVideoResult:
    results: tuple[PublishingResult, ...]

    @property
    def all_succeeded(self) -> bool:
        return all(r.success for r in self.results)

    @property
    def failed(self) -> tuple[PublishingResult, ...]:
        return tuple(r for r in self.results if not r.success)


class PublishVideoUseCase:
    def __init__(self, publishers: list[VideoPublisher]) -> None:
        self._publishers = publishers

    async def execute(self, request: PublishVideoRequest) -> PublishVideoResult:
        async def _publish_one(publisher: VideoPublisher) -> PublishingResult:
            try:
                return await publisher.publish_video(
                    video_list=request.video_list,
                    file_path=request.file_path,
                    title=request.title,
                    description=request.description,
                )
            except Exception as exc:
                logger.exception(
                    "publish.unexpected_error",
                    platform=publisher.platform_name,
                    error=str(exc),
                )
                return PublishingResult(
                    platform=publisher.platform_name,
                    success=False,
                    error=str(exc),
                )

        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_publish_one(p)) for p in self._publishers]

        results = [t.result() for t in tasks]
        for result in results:
            if result.success:
                logger.info("publish.success", platform=result.platform, published_id=result.published_id)
            else:
                logger.error("publish.failed", platform=result.platform, error=result.error)

        return PublishVideoResult(results=tuple(results))


@dataclass(frozen=True)
class WeeklyHorizontalPublishRequest:
    day: date
    yt_title_template: str
    yt_description_template: str
    yt_playlist_id_weekly: str | None
    yt_auth_user_id: str | None


@dataclass(frozen=True)
class WeeklyHorizontalPublishResult:
    already_completed: bool
    published_id: str | None
    persisted_release: bool
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None and (self.already_completed or self.published_id is not None)


class WeeklyHorizontalPublishUseCase:
    def __init__(
        self,
        *,
        release_store: ReleaseStore,
        fetch_top_videos_use_case: FetchTopVideosUseCase,
        horizontal_video_pipeline: HorizontalVideoPipeline,
        uploader: WeeklyYouTubeUploader,
    ) -> None:
        self._release_store = release_store
        self._fetch_top_videos_use_case = fetch_top_videos_use_case
        self._horizontal_video_pipeline = horizontal_video_pipeline
        self._uploader = uploader

    async def execute(self, request: WeeklyHorizontalPublishRequest) -> WeeklyHorizontalPublishResult:
        if self._release_store.is_release_at_date(
            platform=Platform.YOUTUBE.value,
            release_date=request.day,
            release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
        ):
            logger.info("publish_video.already_completed", day=str(request.day))
            return WeeklyHorizontalPublishResult(
                already_completed=True,
                published_id=None,
                persisted_release=False,
            )

        fetch_request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.WEEKLY, day=request.day)
        fetch_result = await self._fetch_top_videos_use_case.execute(fetch_request)
        video_list = rank_videos_by_score(list(fetch_result.videos))

        file_path, thumbnail_path = await self._horizontal_video_pipeline.build_horizontal_video(video_list)

        hashtag_list = extract_video_hashtags(video_list)
        yt_title = generate_youtube_title(
            video_list=video_list,
            title_template=request.yt_title_template,
            hashtags=hashtag_list,
        )
        logger.debug("generated title: ", yt_title=yt_title)

        yt_description = generate_youtube_description(
            video_list=video_list,
            description_template=request.yt_description_template,
        )
        logger.debug("generated description:", yt_description=yt_description)

        try:
            published_id = await self._uploader.upload_weekly_video(
                video_path=file_path,
                title=yt_title,
                description=yt_description,
                thumbnail_path=thumbnail_path,
                playlist_id=request.yt_playlist_id_weekly,
                tags=hashtag_list,
            )
        except Exception as exc:
            logger.exception("publish_video.youtube_upload_failed", error=str(exc))
            return WeeklyHorizontalPublishResult(
                already_completed=False,
                published_id=None,
                persisted_release=False,
                error=str(exc),
            )

        if not published_id:
            return WeeklyHorizontalPublishResult(
                already_completed=False,
                published_id=None,
                persisted_release=False,
                error="empty published id",
            )

        try:
            self._release_store.add_or_update_release(
                Release(
                    platform=Platform.YOUTUBE.value,
                    client_id=request.yt_auth_user_id,
                    release_kind=ReleaseKind.WEEKLY_HORIZONTAL.value,
                    release_id=published_id,
                    published_at=datetime.now(UTC).timestamp(),
                )
            )
            persisted_release = True
        except Exception as exc:
            logger.exception("publish_video.release_persist_failed", error=str(exc))
            persisted_release = False

        return WeeklyHorizontalPublishResult(
            already_completed=False,
            published_id=published_id,
            persisted_release=persisted_release,
        )
