from __future__ import annotations

from unittest.mock import AsyncMock, create_autospec

import pytest

from src.application.fetch_data_use_case import FetchDataUseCase
from src.config.settings import AppSettings, Environment
from src.entrypoints import fetch_data as fetch_data_entrypoint


@pytest.mark.asyncio
async def test_main_async_delegates_to_fetch_data_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_use_case = create_autospec(FetchDataUseCase, instance=True)
    mock_use_case.execute = AsyncMock(return_value=[])

    class _FileExecutionLockStub:
        def __init__(self, _path: object, _operation_name: str) -> None:
            self.acquired = True

        def __enter__(self):
            return self

        def __exit__(self, _exc_type: object, _exc: object, _exc_tb: object) -> bool:
            return False

    settings = AppSettings(
        env=Environment.DEVELOPMENT,
        yt_search_region_code="ES",
        db_video_file="db/db_video.json.test",
        db_data_file="db/db_data.json.test",
        db_timeseries_file="db/db_timeseries.csv.test",
    )

    monkeypatch.setattr(fetch_data_entrypoint, "get_app_settings", lambda: settings)
    monkeypatch.setattr(fetch_data_entrypoint, "FileExecutionLock", _FileExecutionLockStub)
    monkeypatch.setattr(fetch_data_entrypoint, "FetchDataUseCase", lambda *args, **kwargs: mock_use_case)

    await fetch_data_entrypoint.main_async()

    mock_use_case.execute.assert_awaited_once()
