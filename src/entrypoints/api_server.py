"""Run the FastAPI web application."""

import uvicorn
from fastapi import FastAPI

from src.config.settings import get_app_settings
from src.shared.logging import setup_logging
from src.web.main import create_app

API_SERVER_HOST = "0.0.0.0"  # noqa: S104
API_SERVER_PORT = 8080


def bootstrap_app() -> FastAPI:
    """Build and configure the FastAPI app for Uvicorn factory mode."""
    settings = get_app_settings()
    setup_logging(settings.log_file_path)
    return create_app(settings)


def main() -> None:
    """Entry point for the api-server command."""
    uvicorn.run(
        "src.entrypoints.api_server:bootstrap_app",
        host=API_SERVER_HOST,
        port=API_SERVER_PORT,
        factory=True,
    )


if __name__ == "__main__":
    main()
