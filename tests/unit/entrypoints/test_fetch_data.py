from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from src.application.fetch_data_use_case import FetchDataUseCase
from src.config.settings import AppSettings, Environment
from src.entrypoints import fetch_data as fetch_data_entrypoint


class _FileExecutionLockStub:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired

    def __enter__(self):
        return self

    def __exit__(self, _exc_type: object, _exc: object, _exc_tb: object) -> bool:
        return False


def _build_settings() -> AppSettings:
    settings = AppSettings(
        env=Environment.DEVELOPMENT,
        yt_search_region_code="ES",
        db_video_file="db/db_video.json.test",
        db_data_file="db/db_data.json.test",
        db_timeseries_file="db/db_timeseries.csv.test",
    )
    settings.scheduler_lock_file = "/tmp/test.lock"
    return settings


@pytest.mark.asyncio
async def test_main_async_delegates_to_fetch_data_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=[])
    settings = _build_settings()

    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", lambda: settings)
    monkeypatch.setattr(
        fetch_data_entrypoint,
        "FileExecutionLock",
        lambda _path, _operation_name: _FileExecutionLockStub(acquired=True),
    )
    monkeypatch.setattr(fetch_data_entrypoint, "VideoRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "TimeSeriesRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", lambda *args, **kwargs: mock_use_case)

    await fetch_data_entrypoint.main_async()

    mock_use_case.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_async_handles_lock_not_acquired(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock()
    settings = _build_settings()

    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", lambda: settings)
    monkeypatch.setattr(
        fetch_data_entrypoint,
        "FileExecutionLock",
        lambda _path, _operation_name: _FileExecutionLockStub(acquired=False),
    )
    monkeypatch.setattr(fetch_data_entrypoint, "VideoRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "TimeSeriesRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", lambda *args, **kwargs: mock_use_case)

    await fetch_data_entrypoint.main_async()

    mock_use_case.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_async_passes_force_fetch_to_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=[])
    settings = _build_settings()
    received_force: list[bool] = []

    def _build_use_case(*args: Any, **kwargs: Any) -> FetchDataUseCase:
        del args
        received_force.append(kwargs.get("force_fetch", False))
        return mock_use_case

    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", lambda: settings)
    monkeypatch.setattr(
        fetch_data_entrypoint,
        "FileExecutionLock",
        lambda _path, _operation_name: _FileExecutionLockStub(acquired=True),
    )
    monkeypatch.setattr(fetch_data_entrypoint, "VideoRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "TimeSeriesRepository", lambda _path: MagicMock())
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", _build_use_case)

    await fetch_data_entrypoint.main_async(force_fetch=True)

    mock_use_case.execute.assert_awaited_once()
    assert received_force == [True]
