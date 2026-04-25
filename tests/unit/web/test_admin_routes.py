"""Unit tests for admin routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.application.get_setup_page_use_case import GetSetupPageResult
from src.config.settings import AppSettings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.web.dependencies import get_check_platform_connection_use_case, get_setup_page_use_case
from src.web.main import create_app


@dataclass
class _SetupPageUseCaseStub:
    result: GetSetupPageResult

    async def execute(self, _request: object) -> GetSetupPageResult:
        return self.result


@dataclass
class _CheckPlatformConnectionUseCaseStub:
    result: IntegrationCheckResult

    async def execute(self, _request: object) -> IntegrationCheckResult:
        return self.result


def _build_setup_result() -> GetSetupPageResult:
    return GetSetupPageResult(
        yt_authentication_url="https://yt.example/auth",
        yt_credentials=None,
        tiktok_authentication_url="https://tt.example/auth",
        tiktok_credentials=None,
        spotify_authentication_url="https://sp.example/auth",
        spotify_credentials=None,
        is_completed=False,
    )


def _build_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.SPOTIFY,
        status=IntegrationCheckStatus.OK,
        is_configured=True,
        is_publish_target=False,
        message="Spotify account access verified.",
    )


def test_admin_index_redirects_to_login_when_session_missing(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_admin_index_returns_503_when_admin_password_missing(monkeypatch) -> None:
    monkeypatch.delenv("TOP_MUSIC_ADMIN_PASSWORD", raising=False)
    app = create_app(
        AppSettings(
            yt_search_region_code="ES",
            app_secret_key="session-secret",
            admin_password=None,
        )
    )

    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 503


def test_admin_login_accepts_admin_password_env_var(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )

        dashboard_response = client.get("/admin")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/admin"
    assert dashboard_response.status_code == 200
    assert "Platform Connections" in dashboard_response.text


def test_admin_status_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.get("/admin/connections/status")

    assert response.status_code == 403


def test_admin_status_returns_partial_when_authenticated(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        status_response = client.get("/admin/connections/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert status_response.status_code == 200
    assert "connections-grid" in status_response.text
    assert "Check connection" in status_response.text
    assert "Check publish" in status_response.text
    assert "YouTube" in status_response.text


def test_admin_connection_check_returns_single_card_partial(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())
    app.dependency_overrides[get_check_platform_connection_use_case] = lambda: _CheckPlatformConnectionUseCaseStub(
        _build_check_result()
    )

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        check_response = client.post("/admin/connections/spotify/check")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert check_response.status_code == 200
    assert "platform-card-spotify" in check_response.text
    assert "VERIFIED" in check_response.text
    assert "Spotify account access verified." in check_response.text
    rendered_label = next(label for label in ("Check publish", "Check connection") if label in check_response.text)
    assert check_response.text.rindex(rendered_label) < check_response.text.index("platform-card__check-spinner")
