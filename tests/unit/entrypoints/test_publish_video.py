from __future__ import annotations

import pytest

from src.config.settings import AppSettings, Environment
from src.entrypoints.publish_video import _run_weekly_publish_job


class _ReleaseRepositoryStub:
    def __init__(self, _db_path: str) -> None:
        self.checked = True

    def is_release_at_date(self, platform: str, release_date: object, release_kind: str | None = None) -> bool:
        _ = platform, release_date, release_kind
        return True


class _TimeSeriesRepositoryStub:
    def __init__(self, _db_path: str) -> None:
        return


class _VideoRepositoryStub:
    def __init__(self, _db_path: object) -> None:
        return


@pytest.mark.asyncio
async def test_weekly_publish_returns_early_when_already_published(monkeypatch: pytest.MonkeyPatch) -> None:
    execute_called = False

    class _WeeklyUseCaseStub:
        def __init__(
            self,
            *,
            release_store: object,
            fetch_top_videos_use_case: object,
            horizontal_video_pipeline: object,
            uploader: object,
        ) -> None:
            _ = release_store, fetch_top_videos_use_case, horizontal_video_pipeline, uploader

        async def execute(self, request: object):
            nonlocal execute_called
            execute_called = True

            class _Result:
                success = True

            _ = request
            return _Result()

    monkeypatch.setattr("src.entrypoints.publish_video.ReleaseRepository", _ReleaseRepositoryStub)
    monkeypatch.setattr("src.entrypoints.publish_video.TimeSeriesRepository", _TimeSeriesRepositoryStub)
    monkeypatch.setattr("src.entrypoints.publish_video.VideoRepository", _VideoRepositoryStub)
    monkeypatch.setattr("src.entrypoints.publish_video.WeeklyHorizontalPublishUseCase", _WeeklyUseCaseStub)

    await _run_weekly_publish_job(AppSettings(env=Environment.DEVELOPMENT, yt_search_region_code="ES"))

    assert execute_called
