"""Unit tests for publish_vertical entrypoint filtering support."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, sentinel

import pytest

from src.config.settings import AppSettings
from src.entrypoints import publish_vertical


def test_normalize_target_publishers_returns_none_for_empty() -> None:
    assert publish_vertical._normalize_target_publishers(None) is None
    assert publish_vertical._normalize_target_publishers(()) is None


def test_normalize_target_publishers_rejects_invalid_slug() -> None:
    with pytest.raises(ValueError, match="Invalid publisher slug"):
        publish_vertical._normalize_target_publishers(("invalid",))


def test_main_parses_single_publisher_flag() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.publish_vertical.get_app_settings", return_value=settings),
        patch("src.entrypoints.publish_vertical.setup_logging") as setup_logging,
        patch(
            "src.entrypoints.publish_vertical.main_async",
            new=MagicMock(return_value=sentinel.publish_vertical_main_async),
        ) as main_async,
        patch("src.entrypoints.publish_vertical.asyncio.run") as asyncio_run,
        patch("sys.argv", ["publish_vertical.py", "--publisher", "instagram"]),
    ):
        publish_vertical.main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_async.assert_called_once_with(target_publishers=("instagram",))
    asyncio_run.assert_called_once_with(sentinel.publish_vertical_main_async)


def test_main_parses_comma_separated_publishers() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.publish_vertical.get_app_settings", return_value=settings),
        patch("src.entrypoints.publish_vertical.setup_logging"),
        patch(
            "src.entrypoints.publish_vertical.main_async",
            new=MagicMock(return_value=sentinel.publish_vertical_main_async),
        ) as main_async,
        patch("src.entrypoints.publish_vertical.asyncio.run"),
        patch("sys.argv", ["publish_vertical.py", "--publisher", "instagram,tiktok"]),
    ):
        publish_vertical.main()

    main_async.assert_called_once_with(target_publishers=("instagram", "tiktok"))
