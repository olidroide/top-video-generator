"""Smoke tests for the FastAPI web module."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.config.settings import AppSettings
from src.web.main import WEB_DIR, create_app


def test_web_assets_resolve_from_module_directory() -> None:
    assert Path(__file__).resolve().parents[3] / "src/web" == WEB_DIR
    assert (WEB_DIR / "static").is_dir()
    assert (WEB_DIR / "templates").is_dir()


def test_health_route_is_registered() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES"))
    paths = {route.path for route in app.routes}
    assert "/health" in paths


def test_create_app_rejects_missing_production_secret(monkeypatch) -> None:
    monkeypatch.delenv("TOP_MUSIC_APP_SECRET_KEY", raising=False)

    settings = AppSettings(
        env="production",
        yt_search_region_code="ES",
        app_secret_key=None,
    )

    with pytest.raises(RuntimeError, match="TOP_MUSIC_APP_SECRET_KEY"):
        create_app(settings)


def test_create_app_rejects_weak_production_secret() -> None:
    settings = AppSettings(
        env="production",
        yt_search_region_code="ES",
        app_secret_key="too-short",
    )

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        create_app(settings)


def test_create_app_uses_ephemeral_secret_in_development(monkeypatch) -> None:
    monkeypatch.delenv("TOP_MUSIC_APP_SECRET_KEY", raising=False)
    app = create_app(
        AppSettings(
            env="development",
            yt_search_region_code="ES",
            app_secret_key=None,
        )
    )

    assert any("SessionMiddleware" in middleware.cls.__name__ for middleware in app.user_middleware)


def test_admin_session_cookie_is_hardened_in_production() -> None:
    app = create_app(
        AppSettings(
            env="production",
            yt_search_region_code="ES",
            app_secret_key="test-session-secret-with-at-least-32-characters",
        )
    )

    with TestClient(app, base_url="https://testserver") as client:
        response = client.get("/admin/login")

    set_cookie = response.headers.get("set-cookie", "").lower()
    assert "secure" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
