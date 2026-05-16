"""Unit tests for explicit logging bootstrap in entrypoints."""

from unittest.mock import MagicMock, patch, sentinel

from src.config.settings import AppSettings
from src.entrypoints.fetch_data import main as fetch_data_main
from src.entrypoints.publish_vertical import main as publish_vertical_main
from src.entrypoints.publish_video import main as publish_video_main
from src.entrypoints.scheduler import main as scheduler_main
from src.entrypoints.workers.post_processor import main as post_processor_main


def test_fetch_data_main_bootstraps_logging() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.fetch_data.get_app_settings", return_value=settings),
        patch("src.entrypoints.fetch_data.setup_logging") as setup_logging,
        patch(
            "src.entrypoints.fetch_data.main_async",
            new=MagicMock(return_value=sentinel.fetch_data_main_async),
        ) as main_async,
        patch("src.entrypoints.fetch_data.asyncio.run") as asyncio_run,
    ):
        fetch_data_main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_async.assert_called_once_with()
    asyncio_run.assert_called_once_with(sentinel.fetch_data_main_async)


def test_publish_video_main_bootstraps_logging() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.publish_video.get_app_settings", return_value=settings),
        patch("src.entrypoints.publish_video.setup_logging") as setup_logging,
        patch(
            "src.entrypoints.publish_video.main_async",
            new=MagicMock(return_value=sentinel.publish_video_main_async),
        ) as main_async,
        patch("src.entrypoints.publish_video.asyncio.run") as asyncio_run,
    ):
        publish_video_main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_async.assert_called_once_with()
    asyncio_run.assert_called_once_with(sentinel.publish_video_main_async)


def test_publish_vertical_main_bootstraps_logging() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.publish_vertical.get_app_settings", return_value=settings),
        patch("src.entrypoints.publish_vertical.setup_logging") as setup_logging,
        patch(
            "src.entrypoints.publish_vertical.main_async",
            new=MagicMock(return_value=sentinel.publish_vertical_main_async),
        ) as main_async,
        patch("src.entrypoints.publish_vertical.asyncio.run") as asyncio_run,
        patch("sys.argv", ["publish_vertical.py"]),
    ):
        publish_vertical_main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_async.assert_called_once_with(target_publishers=None)
    asyncio_run.assert_called_once_with(sentinel.publish_vertical_main_async)


def test_scheduler_main_bootstraps_logging() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.scheduler.get_app_settings", return_value=settings),
        patch("src.entrypoints.scheduler.setup_logging") as setup_logging,
        patch(
            "src.entrypoints.scheduler.main_async",
            new=MagicMock(return_value=sentinel.scheduler_main_async),
        ) as main_async,
        patch("src.entrypoints.scheduler.asyncio.run") as asyncio_run,
    ):
        scheduler_main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_async.assert_called_once_with()
    asyncio_run.assert_called_once_with(sentinel.scheduler_main_async)


def test_post_processor_main_bootstraps_logging() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.workers.post_processor.get_app_settings", return_value=settings),
        patch("src.entrypoints.workers.post_processor.setup_logging") as setup_logging,
        patch("src.entrypoints.workers.post_processor.main_main") as main_main,
        patch("src.entrypoints.workers.post_processor.sys.argv", ["post_processor.py", "5570 vertical"]),
    ):
        post_processor_main()

    setup_logging.assert_called_once_with(settings.log_file_path)
    main_main.assert_called_once_with(5570, "vertical")
