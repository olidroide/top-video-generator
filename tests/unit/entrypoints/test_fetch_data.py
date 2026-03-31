from __future__ import annotations

from types import SimpleNamespace
from typing import Self

import pytest

from src.config.settings import AppSettings, Environment
from src.domain.models import CanonicalVideo, VideoPoint
from src.entrypoints import fetch_data as fetch_data_entrypoint


@pytest.mark.asyncio
async def test_run_fetch_data_maps_video_metadata_into_video_point(monkeypatch: pytest.MonkeyPatch) -> None:
    added_points: list[VideoPoint] = []
    upserted_videos: list[CanonicalVideo] = []

    class _FileExecutionLockStub:
        def __init__(self, _path: object, _operation_name: str) -> None:
            self.acquired = True

        def __enter__(self) -> Self:
            return self

        def __exit__(self, _exc_type: object, _exc: object, _exc_tb: object) -> bool:
            return False

    class _TimeSeriesRepositoryStub:
        def __init__(self, _db_path: str) -> None:
            return

        def get_last_timestamp(self):
            return None

        def add_video_point(self, video_point: VideoPoint) -> None:
            added_points.append(video_point)

    class _VideoRepositoryStub:
        def __init__(self, _db_path: object) -> None:
            return

        def upsert(self, video: CanonicalVideo) -> None:
            upserted_videos.append(video)

    class _YouTubeSourceStub:
        async def fetch_video_details_batch(self, _video_id_list: list[str]) -> list[CanonicalVideo]:
            return [
                CanonicalVideo(
                    video_id="abc123",
                    title="Test Song",
                    channel_name="Test Channel",
                    views=1000,
                    likes=50,
                    description="Test Description",
                    duration_seconds=182.0,
                )
            ]

    class _FetchTrendingUseCaseStub:
        def __init__(self, source: object) -> None:
            self._source = source

        async def execute(self, _request: object) -> SimpleNamespace:
            return SimpleNamespace(videos=[SimpleNamespace(video_id="abc123")])

    settings = AppSettings(
        env=Environment.DEVELOPMENT,
        yt_search_region_code="ES",
        db_data_file="db/db_data.json.test",
        db_timeseries_file="db/db_timeseries.csv.test",
    )

    monkeypatch.setattr("src.entrypoints.fetch_data.get_app_settings", lambda: settings)
    monkeypatch.setattr("src.entrypoints.fetch_data.FileExecutionLock", _FileExecutionLockStub)
    monkeypatch.setattr("src.entrypoints.fetch_data.TimeSeriesRepository", _TimeSeriesRepositoryStub)
    monkeypatch.setattr("src.entrypoints.fetch_data.VideoRepository", _VideoRepositoryStub)
    monkeypatch.setattr("src.entrypoints.fetch_data.YouTubeSource", _YouTubeSourceStub)
    monkeypatch.setattr("src.entrypoints.fetch_data.FetchTrendingUseCase", _FetchTrendingUseCaseStub)

    await fetch_data_entrypoint.main_async()

    assert len(upserted_videos) == 1
    assert len(added_points) == 1

    video_point = added_points[0]
    assert video_point.title == "Test Song"
    assert video_point.description == "Test Description"
    assert video_point.channel is not None
    assert video_point.channel.name == "Test Channel"
    assert video_point.duration == 182
