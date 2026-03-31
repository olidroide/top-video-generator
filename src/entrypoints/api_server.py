"""Run the FastAPI web application."""

import uvicorn

API_SERVER_HOST = "0.0.0.0"  # noqa: S104
API_SERVER_PORT = 8080


def main() -> None:
    """Entry point for the api-server command."""
    uvicorn.run("src.web.main:app", host=API_SERVER_HOST, port=API_SERVER_PORT)


if __name__ == "__main__":
    main()
