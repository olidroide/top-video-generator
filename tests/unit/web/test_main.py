"""Smoke tests for the FastAPI web module."""

from pathlib import Path

from src.web.main import WEB_DIR, app


def test_web_assets_resolve_from_module_directory() -> None:
    assert Path(__file__).resolve().parents[3] / "src/web" == WEB_DIR
    assert (WEB_DIR / "static").is_dir()
    assert (WEB_DIR / "templates").is_dir()


def test_health_route_is_registered() -> None:
    paths = {route.path for route in app.routes}
    assert "/health" in paths
