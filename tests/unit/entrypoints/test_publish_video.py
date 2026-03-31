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


@pytest.mark.asyncio
async def test_weekly_publish_returns_early_when_already_published(monkeypatch: pytest.MonkeyPatch) -> None:
    fetch_use_case_initialized = False

    class _FetchTopVideosUseCaseGuard:
        def __init__(self, _repo: object) -> None:
            nonlocal fetch_use_case_initialized
            fetch_use_case_initialized = True

    monkeypatch.setattr("src.entrypoints.publish_video.ReleaseRepository", _ReleaseRepositoryStub)
    monkeypatch.setattr("src.entrypoints.publish_video.TimeSeriesRepository", _TimeSeriesRepositoryStub)
    monkeypatch.setattr("src.entrypoints.publish_video.FetchTopVideosUseCase", _FetchTopVideosUseCaseGuard)

    await _run_weekly_publish_job(AppSettings(env=Environment.DEVELOPMENT))

    assert not fetch_use_case_initialized
