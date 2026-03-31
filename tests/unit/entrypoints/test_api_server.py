"""Unit tests for the API server entrypoint."""

from unittest.mock import patch

from src.entrypoints.api_server import API_SERVER_HOST, API_SERVER_PORT, main


def test_main_runs_uvicorn_with_expected_target() -> None:
    with patch("src.entrypoints.api_server.uvicorn.run") as run:
        main()

    run.assert_called_once_with("src.web.main:app", host=API_SERVER_HOST, port=API_SERVER_PORT)
