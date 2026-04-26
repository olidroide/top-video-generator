"""Use case for preparing vertical publish content from ranked videos."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from src.application.fetch_top_videos_use_case import FetchTopVideosRequest, FetchTopVideosUseCase
from src.domain.models import CanonicalVideo, Platform, PublishingResult, Release, ReleaseKind, TimeseriesRange, Video
from src.domain.utils import extract_video_hashtags
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domain.ports import (
        ReleaseStore,
        SpotifyPlaylistUpdater,
        VerticalVideoPipeline,
        VideoPublisher,
        VideoPublishExecutor,
    )

logger = get_logger(__name__)


@dataclass(frozen=True)
class PublishVerticalContentRequest:
    """Input payload for vertical publish content generation."""

    video_list: tuple[Video, ...]
    yt_title_template: str
    yt_description_template: str
    selection_limit: int = 5
    now: datetime | None = None


@dataclass(frozen=True)
class PublishVerticalContentResult:
    """Prepared publish content and selected videos for vertical flow."""

    selected_videos: tuple[Video, ...]
    canonical_video_list: tuple[CanonicalVideo, ...]
    yt_title: str
    yt_description: str
    hashtag_list: tuple[str, ...]


@dataclass(frozen=True)
class VerticalPublishJobContext:
    """Runtime context resolved before executing side effects."""

    pending_publishers: tuple[VideoPublisher, ...]
    spotify_release_pending: bool
    video_list: tuple[Video, ...]

    @property
    def has_any_work(self) -> bool:
        return bool(self.pending_publishers) or self.spotify_release_pending


@dataclass(frozen=True)
class PublisherClientIdentity:
    """Client identifiers used when persisting platform releases."""

    youtube_client_id: str | None
    instagram_client_id: str | None
    tiktok_client_id: str | None


class PublishVerticalUseCase:
    """Prepare selected videos and publish copy for vertical publication."""

    async def maybe_update_spotify_original_playlist(
        self,
        *,
        release_store: ReleaseStore,
        spotify_playlist_updater: SpotifyPlaylistUpdater,
        spotify_release_pending: bool,
        spotify_playlist_original: str | None,
        spotify_user_id: str | None,
        video_list: Sequence[Video],
    ) -> None:
        if not spotify_release_pending:
            return

        playlist_id = spotify_playlist_original
        if not playlist_id:
            return

        try:
            is_authorized = await spotify_playlist_updater.is_authorized()
            if not is_authorized:
                logger.warning(
                    "publish_vertical.spotify_playlist_update_skipped_not_authorized",
                    playlist_id=playlist_id,
                )
                return

            yt_video_title_list = [video.title.split("|")[0].strip() for video in video_list if video.title]
            await spotify_playlist_updater.update_original_playlist(
                playlist_id=playlist_id,
                song_title_list=yt_video_title_list,
            )
            self.persist_spotify_release(
                release_store=release_store,
                spotify_user_id=spotify_user_id,
                spotify_playlist_original=spotify_playlist_original,
            )
        except Exception as exc:
            logger.exception("publish_vertical.spotify_playlist_update_failed", error=str(exc))

    async def publish_pending_vertical_videos(
        self,
        *,
        release_store: ReleaseStore,
        publish_executor: VideoPublishExecutor,
        vertical_video_pipeline: VerticalVideoPipeline,
        pending_publishers: Sequence[VideoPublisher],
        video_list: Sequence[Video],
        publisher_client_identity: PublisherClientIdentity,
        yt_title_template: str,
        yt_description_template: str,
    ) -> None:
        if not pending_publishers:
            return

        content = self.execute(
            PublishVerticalContentRequest(
                video_list=tuple(video_list),
                yt_title_template=yt_title_template,
                yt_description_template=yt_description_template,
            )
        )

        selected_videos = list(content.selected_videos)
        file_path = await vertical_video_pipeline.build_vertical_video(selected_videos)

        yt_title = content.yt_title
        logger.debug("generated title: ", yt_title=yt_title)
        yt_description = content.yt_description
        logger.debug("generated description:", yt_description=yt_description)

        async def _publish_one(publisher: VideoPublisher) -> PublishingResult:
            description = yt_description if publisher.platform_name == Platform.YOUTUBE else yt_title
            return await publish_executor.publish(
                publisher=publisher,
                video_list=content.canonical_video_list,
                file_path=file_path,
                title=yt_title,
                description=description,
            )

        async with asyncio.TaskGroup() as task_group:
            tasks = [(publisher, task_group.create_task(_publish_one(publisher))) for publisher in pending_publishers]

        for publisher, task in tasks:
            result = task.result()
            if not result.success:
                continue
            self.persist_publisher_release(
                release_store=release_store,
                publisher=publisher,
                result=result,
                publisher_client_identity=publisher_client_identity,
            )

    async def build_job_context(
        self,
        *,
        release_store: ReleaseStore,
        publishers: Sequence[VideoPublisher],
        fetch_top_videos_use_case: FetchTopVideosUseCase,
        day: date,
        spotify_playlist_original: str | None,
        is_spotify_configured: bool,
    ) -> VerticalPublishJobContext:
        pending_publishers = self.pending_publishers(
            release_store=release_store,
            publishers=publishers,
            day=day,
        )
        spotify_release_pending = self.is_spotify_release_pending(
            release_store=release_store,
            spotify_playlist_original=spotify_playlist_original,
            is_spotify_configured=is_spotify_configured,
            day=day,
        )

        if not pending_publishers and not spotify_release_pending:
            return VerticalPublishJobContext(
                pending_publishers=(),
                spotify_release_pending=False,
                video_list=(),
            )

        fetch_request = FetchTopVideosRequest(timeseries_range=TimeseriesRange.DAILY, day=day)
        result = await fetch_top_videos_use_case.execute(fetch_request)

        return VerticalPublishJobContext(
            pending_publishers=pending_publishers,
            spotify_release_pending=spotify_release_pending,
            video_list=result.videos,
        )

    def pending_publishers(
        self,
        *,
        release_store: ReleaseStore,
        publishers: Sequence[VideoPublisher],
        day: date,
    ) -> tuple[VideoPublisher, ...]:
        return tuple(
            publisher
            for publisher in publishers
            if not release_store.is_release_at_date(
                platform=publisher.platform_name.value,
                release_date=day,
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
            )
        )

    def is_spotify_release_pending(
        self,
        *,
        release_store: ReleaseStore,
        spotify_playlist_original: str | None,
        is_spotify_configured: bool,
        day: date,
    ) -> bool:
        if not (spotify_playlist_original and is_spotify_configured):
            return False
        return not release_store.is_release_at_date(
            platform=Platform.SPOTIFY.value,
            release_date=day,
            release_kind=ReleaseKind.DAILY_VERTICAL.value,
        )

    def persist_spotify_release(
        self,
        *,
        release_store: ReleaseStore,
        spotify_user_id: str | None,
        spotify_playlist_original: str | None,
        now: datetime | None = None,
    ) -> None:
        if not spotify_playlist_original:
            return

        reference = now or datetime.now(UTC)
        release_store.add_or_update_release(
            Release(
                platform=Platform.SPOTIFY.value,
                client_id=spotify_user_id,
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
                release_id=spotify_playlist_original,
                published_at=reference.timestamp(),
            )
        )

    def persist_publisher_release(
        self,
        *,
        release_store: ReleaseStore,
        publisher: VideoPublisher,
        result: PublishingResult,
        publisher_client_identity: PublisherClientIdentity,
        now: datetime | None = None,
    ) -> None:
        reference = now or datetime.now(UTC)
        release_store.add_or_update_release(
            Release(
                platform=publisher.platform_name.name,
                client_id=self._publisher_client_id(publisher.platform_name.value, publisher_client_identity),
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
                release_id=result.published_id,
                published_at=result.published_at.timestamp() if result.published_at else reference.timestamp(),
            )
        )

    def execute(self, request: PublishVerticalContentRequest) -> PublishVerticalContentResult:
        selected_videos = self._select_videos(request.video_list, request.selection_limit)
        hashtag_list = tuple(extract_video_hashtags(list(selected_videos)))

        now = request.now or datetime.now(UTC)
        yt_title = self._generate_yt_title(
            video_list=selected_videos,
            hashtag_list=hashtag_list,
            yt_title_template=request.yt_title_template,
            now=now,
        )
        yt_description = self._generate_yt_description(
            video_list=selected_videos,
            yt_description_template=request.yt_description_template,
            now=now,
        )

        canonical_video_list = tuple(self._video_to_canonical(video) for video in selected_videos)

        return PublishVerticalContentResult(
            selected_videos=selected_videos,
            canonical_video_list=canonical_video_list,
            yt_title=yt_title,
            yt_description=yt_description,
            hashtag_list=hashtag_list,
        )

    @staticmethod
    def _select_videos(video_list: tuple[Video, ...], limit: int) -> tuple[Video, ...]:
        selected = list(video_list[:limit])
        selected.sort(
            key=lambda video: (video.score is None, video.score if video.score is not None else 0),
            reverse=True,
        )
        return tuple(selected)

    @staticmethod
    def _generate_yt_title(
        video_list: tuple[Video, ...],
        hashtag_list: tuple[str, ...],
        yt_title_template: str,
        now: datetime,
    ) -> str:
        text_date = now.astimezone(UTC).strftime("%d/%m/%Y")
        hashtags = " ".join(hashtag_list) if hashtag_list else ""
        return yt_title_template.replace("@@TOP_DATE@@", f"[{text_date}] #top{len(video_list)}").replace(
            "@@HASHTAGS@@", f"\n{hashtags}"
        )

    @staticmethod
    def _generate_yt_description(
        video_list: tuple[Video, ...],
        yt_description_template: str,
        now: datetime,
    ) -> str:
        text_date = now.astimezone(UTC).strftime("%d / %m / %Y")

        channels_names = list(
            {(video.channel.name if video.channel and video.channel.name else "") for video in video_list}
        )
        channels_names = [name for name in channels_names if name]
        original_publishers = ", ".join(channels_names)

        fair_use_text = (
            "As per the 3rd section of fair use guidelines borrowing small bits of material from "
            "an original work is more likely to be considered fair use. Copyright disclaimer under "
            "section 107 of the copyright act 1976, allowance is made for fair use"
        )
        legal_notice = (
            "This publication and the information included in it are not intended to serve "
            "a substitute for consultation with an attonery."
        )
        copyright_notice = (
            "Please note no copyright infringement is intended, and I do not own nor claim to own "
            "any of the original publishers recordings used in this video. "
            f"Original publishers : {original_publishers}."
        )
        disclaimer = f"------\nDisclaimer\n  - {legal_notice}\n\n  - {copyright_notice}\n\n  - {fair_use_text}\n------"

        video_list_names = ""
        for video in video_list:
            score = video.score if video.score is not None else "-"
            title = video.title_cleaned or (video.title or "")
            url = video.yt_video_url
            video_list_names += f"{score}.- {title} {url} \n"
            if video.channel and video.channel.name:
                video_list_names += f"© {video.channel.name}\n\n"

        return (
            yt_description_template.replace("@@TOP_DATE@@", f"{text_date} #top{len(video_list)}")
            .replace("@@VIDEO_LIST@@", f"{video_list_names}")
            .replace("@@DISCLAIMER@@", disclaimer)
        )

    @staticmethod
    def _video_to_canonical(video: Video) -> CanonicalVideo:
        return CanonicalVideo(
            video_id=video.video_id,
            title=video.title or "",
            channel_name=video.channel.name if video.channel and video.channel.name else "",
            views=video.views,
            views_growth=video.views_growth or 0,
            score=float(video.score) if video.score is not None else 0.0,
            score_previous=float(video.score_previous) if video.score_previous is not None else 0.0,
            thumbnail_url=video.yt_video_thumbnail_url,
        )

    @staticmethod
    def _publisher_client_id(platform_name: str, publisher_client_identity: PublisherClientIdentity) -> str | None:
        if platform_name == Platform.INSTAGRAM.value:
            return publisher_client_identity.instagram_client_id
        if platform_name == Platform.TIKTOK.value:
            return publisher_client_identity.tiktok_client_id
        return publisher_client_identity.youtube_client_id
