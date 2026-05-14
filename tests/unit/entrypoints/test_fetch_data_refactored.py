from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from src.application.fetch_data_use_case import FetchDataUseCase
from src.config.settings import AppSettings, Environment
from src.entrypoints import fetch_data as fetch_data_entrypoint


@pytest.mark.asyncio
async def test_main_async_calls_fetch_data_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that main_async delegates to FetchDataUseCase."""
    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=[])

    class _FileExecutionLockStub:
        def __init__(self, _path: object, _operation_name: str) -> None:
            self.acquired = True

        def __enter__(self):
            return self

        def __exit__(self, _exc_type: object, _exc: object, _exc_tb: object) -> bool:
            return False

    def _get_app_settings() -> AppSettings:
        settings = AppSettings(
            env=Environment.DEVELOPMENT,
            yt_search_region_code="ES",
            db_video_file="db/db_video.json.test",
            db_data_file="db/db_data.json.test",
            db_timeseries_file="db/db_timeseries.csv.test",
        )
        settings.scheduler_lock_file = "/tmp/test.lock"
        return settings

    monkeypatch.setattr(fetch_data_entrypoint, "FileExecutionLock", _FileExecutionLockStub)
    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", _get_app_settings)
    monkeypatch.setattr(fetch_data_entrypoint, "VideoRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "TimeSeriesRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", lambda *args, **kwargs: mock_use_case)

    await fetch_data_entrypoint.main_async()

    mock_use_case.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_async_handles_lock_not_acquired(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that main_async exits early when lock not acquired."""

    class _FileExecutionLockStub:
        def __init__(self, _path: object, _operation_name: str) -> None:
            self.acquired = False  # Simulate lock not acquired

        def __enter__(self):
            return self

        def __exit__(self, _exc_type: object, _exc: object, _exc_tb: object) -> bool:
            return False

    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock()

    def _get_app_settings() -> AppSettings:
        settings = AppSettings(
            env=Environment.DEVELOPMENT,
            yt_search_region_code="ES",
            db_video_file="db/db_video.json.test",
            db_data_file="db/db_data.json.test",
            db_timeseries_file="db/db_timeseries.csv.test",
        )
        settings.scheduler_lock_file = "/tmp/test.lock"
        return settings

    monkeypatch.setattr(fetch_data_entrypoint, "FileExecutionLock", _FileExecutionLockStub)
    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", _get_app_settings)
    monkeypatch.setattr(fetch_data_entrypoint, "VideoRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "TimeSeriesRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", lambda *args, **kwargs: mock_use_case)

    await fetch_data_entrypoint.main_async()

    # Should not call use case when lock not acquired
    mock_use_case.execute.assert_not_awaited()
