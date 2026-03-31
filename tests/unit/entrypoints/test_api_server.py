"""Unit tests for the API server entrypoint."""

from unittest.mock import patch, sentinel

from src.config.settings import AppSettings
from src.entrypoints.api_server import API_SERVER_HOST, API_SERVER_PORT, bootstrap_app, main


def test_main_runs_uvicorn_with_expected_target() -> None:
    with patch("src.entrypoints.api_server.uvicorn.run") as run:
        main()

    run.assert_called_once_with(
        "src.entrypoints.api_server:bootstrap_app",
        host=API_SERVER_HOST,
        port=API_SERVER_PORT,
        factory=True,
    )


def test_bootstrap_app_initializes_logging_and_builds_web_app() -> None:
    settings = AppSettings(yt_search_region_code="ES")

    with (
        patch("src.entrypoints.api_server.get_app_settings", return_value=settings),
        patch("src.entrypoints.api_server.setup_logging") as setup_logging,
        patch("src.entrypoints.api_server.create_app", return_value=sentinel.app) as create_app,
    ):
        app = bootstrap_app()

    setup_logging.assert_called_once_with(settings.log_file_path)
    create_app.assert_called_once_with(settings)
    assert app is sentinel.app
