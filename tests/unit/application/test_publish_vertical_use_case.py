"""Unit tests for PublishVerticalUseCase."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.application.fetch_top_videos_use_case import FetchTopVideosResult
from src.application.publish_vertical_use_case import (
    PublisherClientIdentity,
    PublishVerticalContentRequest,
    PublishVerticalUseCase,
)
from src.domain.models import Channel, Platform, PublishingResult, Release, Video, VideoScoreStatus


def make_video(
    video_id: str,
    *,
    score: int | None = None,
    score_previous: int | None = None,
    views: int = 1000,
    views_growth: int | None = None,
    title: str | None = None,
    description: str | None = None,
    channel_name: str | None = None,
) -> Video:
    return Video(
        video_id=video_id,
        score=score,
        score_previous=score_previous,
        score_status=VideoScoreStatus.NEW,
        views=views,
        views_growth=views_growth,
        likes=100,
        title=title or f"Song {video_id} Official Video",
        description=description or "#pop #viral",
        channel=Channel(name=channel_name) if channel_name else None,
    )


class TestPublishVerticalUseCase:
    def test_execute_selects_top_five_with_legacy_ordering(self) -> None:
        videos = tuple(make_video(f"v{i}", score=i) for i in range(1, 8))
        use_case = PublishVerticalUseCase()

        result = use_case.execute(
            PublishVerticalContentRequest(
                video_list=videos,
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@\n@@DISCLAIMER@@",
                now=datetime(2026, 4, 25, 10, 30, tzinfo=UTC),
            )
        )

        assert len(result.selected_videos) == 5
        assert [v.video_id for v in result.selected_videos] == ["v5", "v4", "v3", "v2", "v1"]

    def test_execute_builds_title_description_and_canonical_payload(self) -> None:
        videos = (
            make_video("v1", score=1, score_previous=2, title="Track One (Video)", channel_name="Artist A"),
            make_video("v2", score=2, title="Track Two Official Video", channel_name="Artist B"),
        )
        use_case = PublishVerticalUseCase()

        result = use_case.execute(
            PublishVerticalContentRequest(
                video_list=videos,
                yt_title_template="Top @@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="Date: @@TOP_DATE@@\n@@VIDEO_LIST@@\n@@DISCLAIMER@@",
                now=datetime(2026, 4, 25, 10, 30, tzinfo=UTC),
            )
        )

        assert "[25/04/2026] #top2" in result.yt_title
        assert "#pop" in result.yt_title
        assert "Date: 25 / 04 / 2026 #top2" in result.yt_description
        assert "1.- Track One" in result.yt_description
        assert "2.- Track Two" in result.yt_description
        assert "© Artist A" in result.yt_description
        assert len(result.canonical_video_list) == 2
        assert result.canonical_video_list[0].video_id == "v2"
        assert result.canonical_video_list[0].score == 2.0

    def test_execute_does_not_mutate_input_videos(self) -> None:
        videos = (
            make_video("v1", score=1),
            make_video("v2", score=2),
        )
        original_scores = [video.score for video in videos]

        use_case = PublishVerticalUseCase()
        _ = use_case.execute(
            PublishVerticalContentRequest(
                video_list=videos,
                yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
                yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@\n@@DISCLAIMER@@",
                now=datetime(2026, 4, 25, 10, 30, tzinfo=UTC),
            )
        )

        assert [video.score for video in videos] == original_scores

    def test_pending_publishers_excludes_already_published_platforms(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self) -> None:
                self._published = {Platform.YOUTUBE.value}

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del release_date, release_kind
                return platform in self._published

            def add_or_update_release(self, release: Release) -> None:
                del release

        use_case = PublishVerticalUseCase()
        publishers = (
            SimpleNamespace(platform_name=Platform.YOUTUBE),
            SimpleNamespace(platform_name=Platform.TIKTOK),
        )

        pending = use_case.pending_publishers(
            release_store=_ReleaseStoreFake(),
            publishers=publishers,
            day=datetime(2026, 4, 25, tzinfo=UTC).date(),
        )

        assert len(pending) == 1
        assert pending[0].platform_name == Platform.TIKTOK

    def test_is_spotify_release_pending_checks_config_and_existing_release(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self, released: bool) -> None:
                self._released = released

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return self._released

            def add_or_update_release(self, release: Release) -> None:
                del release

        use_case = PublishVerticalUseCase()
        day = datetime(2026, 4, 25, tzinfo=UTC).date()

        assert use_case.is_spotify_release_pending(
            release_store=_ReleaseStoreFake(released=False),
            spotify_playlist_original="pl_123",
            is_spotify_configured=True,
            day=day,
        )
        assert not use_case.is_spotify_release_pending(
            release_store=_ReleaseStoreFake(released=True),
            spotify_playlist_original="pl_123",
            is_spotify_configured=True,
            day=day,
        )
        assert not use_case.is_spotify_release_pending(
            release_store=_ReleaseStoreFake(released=False),
            spotify_playlist_original=None,
            is_spotify_configured=True,
            day=day,
        )

    def test_persist_publisher_release_uses_expected_client_id(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self) -> None:
                self.saved: list[Release] = []

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> None:
                self.saved.append(release)

        use_case = PublishVerticalUseCase()
        release_store = _ReleaseStoreFake()
        publisher = SimpleNamespace(platform_name=Platform.INSTAGRAM)
        result = PublishingResult(
            platform=Platform.INSTAGRAM,
            success=True,
            published_id="ig_123",
            published_at=datetime(2026, 4, 25, 13, 0, tzinfo=UTC),
        )

        use_case.persist_publisher_release(
            release_store=release_store,
            publisher=publisher,
            result=result,
            publisher_client_identity=PublisherClientIdentity(
                youtube_client_id="yt_owner",
                instagram_client_id="ig_owner",
                tiktok_client_id="tt_owner",
            ),
        )

        assert len(release_store.saved) == 1
        saved = release_store.saved[0]
        assert saved.platform == Platform.INSTAGRAM.value
        assert saved.client_id == "ig_owner"
        assert saved.release_id == "ig_123"

    def test_persist_spotify_release_skips_when_playlist_missing(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self) -> None:
                self.saved: list[Release] = []

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> None:
                self.saved.append(release)

        use_case = PublishVerticalUseCase()
        release_store = _ReleaseStoreFake()

        use_case.persist_spotify_release(
            release_store=release_store,
            spotify_user_id="sp_owner",
            spotify_playlist_original=None,
        )

        assert release_store.saved == []

    @pytest.mark.asyncio
    async def test_build_job_context_skips_fetch_when_no_work(self) -> None:
        class _ReleaseStoreFake:
            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return True

            def add_or_update_release(self, release: Release) -> Release:
                return release

        fetch_use_case = SimpleNamespace(execute=AsyncMock())
        use_case = PublishVerticalUseCase()

        context = await use_case.build_job_context(
            release_store=_ReleaseStoreFake(),
            publishers=(SimpleNamespace(platform_name=Platform.YOUTUBE),),
            fetch_top_videos_use_case=fetch_use_case,
            day=datetime(2026, 4, 25, tzinfo=UTC).date(),
            spotify_playlist_original=None,
            is_spotify_configured=False,
        )

        assert not context.has_any_work
        assert context.video_list == ()
        fetch_use_case.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_build_job_context_fetches_videos_when_work_pending(self) -> None:
        class _ReleaseStoreFake:
            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del release_date, release_kind
                return platform == Platform.SPOTIFY.value

            def add_or_update_release(self, release: Release) -> Release:
                return release

        videos = (make_video("v1", score=1),)
        fetch_use_case = SimpleNamespace(execute=AsyncMock(return_value=FetchTopVideosResult(videos=videos)))
        use_case = PublishVerticalUseCase()

        context = await use_case.build_job_context(
            release_store=_ReleaseStoreFake(),
            publishers=(SimpleNamespace(platform_name=Platform.YOUTUBE),),
            fetch_top_videos_use_case=fetch_use_case,
            day=datetime(2026, 4, 25, tzinfo=UTC).date(),
            spotify_playlist_original="playlist_1",
            is_spotify_configured=True,
        )

        assert context.has_any_work
        assert len(context.pending_publishers) == 1
        assert context.video_list == videos
        fetch_use_case.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_publish_pending_vertical_videos_persists_only_successful_results(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self) -> None:
                self.saved: list[Release] = []

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> Release:
                self.saved.append(release)
                return release

        class _VerticalPipelineFake:
            def __init__(self) -> None:
                self.called_with: list[Video] = []

            async def build_vertical_video(self, video_list: list[Video]) -> str:
                self.called_with = video_list
                return "/tmp/final-vertical.mp4"

        class _PublishExecutorFake:
            def __init__(self) -> None:
                self.calls: list[tuple[str, str, str]] = []

            async def publish(
                self,
                publisher: SimpleNamespace,
                video_list: tuple,
                file_path: str,
                title: str,
                description: str,
            ) -> PublishingResult:
                del video_list, title
                self.calls.append((publisher.platform_name.value, file_path, description))
                if publisher.platform_name == Platform.TIKTOK:
                    return PublishingResult(platform=Platform.TIKTOK, success=False, error="fail")
                return PublishingResult(platform=publisher.platform_name, success=True, published_id="ok")

        use_case = PublishVerticalUseCase()
        release_store = _ReleaseStoreFake()
        pipeline = _VerticalPipelineFake()
        executor = _PublishExecutorFake()
        publishers = (
            SimpleNamespace(platform_name=Platform.YOUTUBE),
            SimpleNamespace(platform_name=Platform.TIKTOK),
        )
        videos = (
            make_video("v1", score=1, channel_name="A"),
            make_video("v2", score=2, channel_name="B"),
        )

        await use_case.publish_pending_vertical_videos(
            release_store=release_store,
            publish_executor=executor,
            vertical_video_pipeline=pipeline,
            pending_publishers=publishers,
            video_list=videos,
            publisher_client_identity=PublisherClientIdentity(
                youtube_client_id="yt-owner",
                instagram_client_id="ig-owner",
                tiktok_client_id="tt-owner",
            ),
            yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
            yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@\n@@DISCLAIMER@@",
        )

        assert len(pipeline.called_with) == 2
        assert len(executor.calls) == 2
        assert executor.calls[0][1] == "/tmp/final-vertical.mp4"
        assert len(release_store.saved) == 1
        assert release_store.saved[0].platform == Platform.YOUTUBE.value

    @pytest.mark.asyncio
    async def test_publish_pending_vertical_videos_skips_when_no_publishers(self) -> None:
        class _ReleaseStoreFake:
            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> Release:
                return release

        class _VerticalPipelineFake:
            def __init__(self) -> None:
                self.calls = 0

            async def build_vertical_video(self, video_list: list[Video]) -> str:
                del video_list
                self.calls += 1
                return "/tmp/final-vertical.mp4"

        class _PublishExecutorFake:
            async def publish(
                self,
                publisher: SimpleNamespace,
                video_list: tuple,
                file_path: str,
                title: str,
                description: str,
            ) -> PublishingResult:
                del publisher, video_list, file_path, title, description
                return PublishingResult(platform=Platform.YOUTUBE, success=True, published_id="ok")

        use_case = PublishVerticalUseCase()
        pipeline = _VerticalPipelineFake()

        await use_case.publish_pending_vertical_videos(
            release_store=_ReleaseStoreFake(),
            publish_executor=_PublishExecutorFake(),
            vertical_video_pipeline=pipeline,
            pending_publishers=(),
            video_list=(make_video("v1", score=1),),
            publisher_client_identity=PublisherClientIdentity(
                youtube_client_id="yt-owner",
                instagram_client_id="ig-owner",
                tiktok_client_id="tt-owner",
            ),
            yt_title_template="@@TOP_DATE@@ @@HASHTAGS@@",
            yt_description_template="@@TOP_DATE@@\n@@VIDEO_LIST@@\n@@DISCLAIMER@@",
        )

        assert pipeline.calls == 0

    @pytest.mark.asyncio
    async def test_maybe_update_spotify_original_playlist_persists_release_on_success(self) -> None:
        class _ReleaseStoreFake:
            def __init__(self) -> None:
                self.saved: list[Release] = []

            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> Release:
                self.saved.append(release)
                return release

        class _SpotifyUpdaterFake:
            def __init__(self) -> None:
                self.called = False

            async def update_original_playlist(self, playlist_id: str, song_title_list: list[str]) -> bool:
                del song_title_list
                self.called = playlist_id == "playlist_1"
                return True

        use_case = PublishVerticalUseCase()
        release_store = _ReleaseStoreFake()
        updater = _SpotifyUpdaterFake()

        await use_case.maybe_update_spotify_original_playlist(
            release_store=release_store,
            spotify_playlist_updater=updater,
            spotify_release_pending=True,
            spotify_playlist_original="playlist_1",
            spotify_user_id="sp-owner",
            video_list=(make_video("v1", title="Song A | Live"), make_video("v2", title="Song B")),
        )

        assert updater.called
        assert len(release_store.saved) == 1
        assert release_store.saved[0].platform == Platform.SPOTIFY.value

    @pytest.mark.asyncio
    async def test_maybe_update_spotify_original_playlist_skips_when_not_pending(self) -> None:
        class _ReleaseStoreFake:
            def is_release_at_date(
                self,
                platform: str,
                release_date: datetime.date,
                release_kind: str | None = None,
            ) -> bool:
                del platform, release_date, release_kind
                return False

            def add_or_update_release(self, release: Release) -> Release:
                return release

        class _SpotifyUpdaterFake:
            def __init__(self) -> None:
                self.called = False

            async def update_original_playlist(self, playlist_id: str, song_title_list: list[str]) -> bool:
                del playlist_id, song_title_list
                self.called = True
                return True

        use_case = PublishVerticalUseCase()
        updater = _SpotifyUpdaterFake()

        await use_case.maybe_update_spotify_original_playlist(
            release_store=_ReleaseStoreFake(),
            spotify_playlist_updater=updater,
            spotify_release_pending=False,
            spotify_playlist_original="playlist_1",
            spotify_user_id="sp-owner",
            video_list=(make_video("v1"),),
        )

        assert not updater.called
