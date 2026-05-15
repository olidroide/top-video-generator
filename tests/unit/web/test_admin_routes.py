"""Unit tests for admin routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.application.get_operational_metrics_use_case import OperationalMetricsResult
from src.application.get_setup_page_use_case import GetSetupPageResult
from src.config.settings import AppSettings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.web.dependencies import (
    get_check_platform_connection_use_case,
    get_operational_metrics_use_case,
    get_setup_page_use_case,
)
from src.web.main import create_app
from src.web.state import get_app_version


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


@dataclass
class _OperationalMetricsUseCaseStub:
    result: OperationalMetricsResult

    def execute(self) -> OperationalMetricsResult:
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


def _build_instagram_not_configured_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.INSTAGRAM,
        status=IntegrationCheckStatus.NOT_CONFIGURED,
        is_configured=False,
        is_publish_target=True,
        message="Missing Instagram credentials or dependency.",
    )


def _build_spotify_reauth_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.SPOTIFY,
        status=IntegrationCheckStatus.ERROR,
        is_configured=True,
        is_publish_target=False,
        message="Spotify authorization is invalid or expired. Reconnect Spotify from Setup.",
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
    assert f"v{get_app_version()}" in dashboard_response.text


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


def test_admin_health_status_returns_partial(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        health_response = client.get("/admin/health/status")

    assert login_response.status_code == 303
    assert health_response.status_code == 200
    assert "health-checks" in health_response.text
    assert "Database accessible" in health_response.text


def test_admin_metrics_status_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.get("/admin/metrics/status")

    assert response.status_code == 403


def test_admin_metrics_status_returns_partial_when_authenticated(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_operational_metrics_use_case] = lambda: _OperationalMetricsUseCaseStub(
        OperationalMetricsResult(
            fetch_count=10,
            fetch_errors=2,
            upload_count=3,
            upload_errors=1,
            processing_count=5,
            processing_errors=0,
        )
    )

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        response = client.get("/admin/metrics/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "metrics-grid" in response.text
    assert "FETCH" in response.text
    assert "COUNT" in response.text
    assert "ERROR RATE" in response.text


def test_admin_dashboard_renders_metrics_section(monkeypatch) -> None:
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
    assert dashboard_response.status_code == 200
    assert "Runtime Metrics" in dashboard_response.text
    assert 'hx-get="/admin/metrics/status"' in dashboard_response.text


def test_admin_task_trigger_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.post("/admin/tasks/fetch/trigger")

    assert response.status_code == 403


def test_admin_task_trigger_returns_400_for_invalid_method(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        response = client.post("/admin/tasks/not-a-method/trigger")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 400
    assert "Invalid task method" in response.text


def test_admin_task_trigger_returns_feedback_fragment_when_authenticated(monkeypatch) -> None:
    from src.entrypoints import fetch_data

    async def _fake_fetch_main_async() -> None:
        return None

    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setattr(fetch_data, "main_async", _fake_fetch_main_async)
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        response = client.post("/admin/tasks/fetch/trigger")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert 'id="tasks-feedback"' in response.text
    assert "Accepted:" in response.text
    assert "Task &#39;fetch&#39; ready for execution." in response.text


def test_admin_connection_check_instagram_not_configured_aligns_card_state(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(
        AppSettings(
            yt_search_region_code="ES",
            app_secret_key="session-secret",
            instagram_client_username="ig-user",
            instagram_client_password="ig-pass",
        )
    )
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())
    app.dependency_overrides[get_check_platform_connection_use_case] = lambda: _CheckPlatformConnectionUseCaseStub(
        _build_instagram_not_configured_check_result()
    )

    with TestClient(app) as client:
        login_response = client.post(
            "/admin/login",
            data={"password": "admin-pass"},
            follow_redirects=False,
        )
        check_response = client.post("/admin/connections/instagram/check")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert check_response.status_code == 200
    assert "platform-card-instagram" in check_response.text
    assert "Status: NOT CONFIGURED" in check_response.text
    assert "Missing Instagram credentials or dependency." in check_response.text
    assert 'n-status__label--na">NOT CONFIGURED</span>' in check_response.text
    assert "Check publish" in check_response.text
    assert 'hx-post="/admin/connections/instagram/check"' in check_response.text
    assert '<button\n      disabled\n      class="secondary outline"' in check_response.text


def test_admin_connection_check_spotify_reauth_required(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())
    app.dependency_overrides[get_check_platform_connection_use_case] = lambda: _CheckPlatformConnectionUseCaseStub(
        _build_spotify_reauth_check_result()
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
    assert "REAUTH REQUIRED" in check_response.text
    assert "Reconnect Spotify from Setup." in check_response.text
