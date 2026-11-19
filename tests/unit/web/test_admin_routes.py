"""Unit tests for admin routes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from src.application.get_admin_task_status_use_case import TaskStatusResult
from src.application.get_operational_metrics_use_case import OperationalMetricsResult
from src.application.get_setup_page_use_case import GetSetupPageResult
from src.application.trigger_admin_task_use_case import TriggerAdminTaskRequest, TriggerAdminTaskResult
from src.config.settings import AppSettings
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.web.dependencies import (
    get_admin_task_status_use_case,
    get_check_platform_connection_use_case,
    get_operational_metrics_use_case,
    get_publisher_state_repo,
    get_release_repo,
    get_setup_page_use_case,
    get_trigger_admin_task_use_case,
)
from src.web.main import create_app
from src.web.state import get_app_version


def _login_admin(client: TestClient) -> object:
    login_page = client.get("/admin/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text)
    assert match is not None
    csrf_token = match.group(1)
    client.headers["X-CSRF-Token"] = csrf_token
    client.headers["HX-Request"] = "true"
    return client.post(
        "/admin/login",
        data={"password": "admin-pass", "csrf_token": csrf_token},
        follow_redirects=False,
    )


@dataclass
class _SetupPageUseCaseStub:
    result: GetSetupPageResult

    async def execute(self, _request: object) -> GetSetupPageResult:
        return self.result


@dataclass
class _TriggerAdminTaskUseCaseStub:
    completed_methods: list[str]
    failed_methods: list[tuple[str, str]]

    def preflight(self, request: TriggerAdminTaskRequest) -> TriggerAdminTaskResult:
        return TriggerAdminTaskResult(
            queued=True,
            message=f"Task '{request.task_method}' scheduled. Background execution will begin shortly.",
            normalized_publisher=request.publisher.lower() if request.publisher else None,
        )

    def execute(self, request: TriggerAdminTaskRequest) -> TriggerAdminTaskResult:
        return self.preflight(request)

    async def execute_tracked(
        self,
        request: TriggerAdminTaskRequest,
        task,
    ) -> bool:
        preflight = self.preflight(request)
        if not preflight.queued:
            return False
        acquired = await task()
        if acquired is False:
            self.mark_failed(
                task_method=request.task_method,
                error_message="Task skipped because the execution lock is busy.",
            )
            return False
        self.mark_completed(task_method=request.task_method)
        return True

    def mark_completed(self, *, task_method: str) -> None:
        self.completed_methods.append(task_method)

    def mark_failed(self, *, task_method: str, error_message: str) -> None:
        self.failed_methods.append((task_method, error_message))


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


@dataclass
class _AdminTaskStatusUseCaseStub:
    result: TaskStatusResult

    def execute(self) -> TaskStatusResult:
        return self.result

    def get_task_started_at(self, _task_method: str) -> float | None:
        return None


@dataclass
class _PublisherStateStub:
    enabled_by_slug: dict[str, bool]

    def is_enabled(self, platform: str) -> bool:
        return self.enabled_by_slug.get(platform, True)

    def set_enabled(self, platform: str, enabled: bool) -> None:
        self.enabled_by_slug[platform] = enabled


class _ReleaseRepoStub:
    def get_latest_release(self, *, platform: str, release_kind: str):
        _ = platform, release_kind


def _build_setup_result() -> GetSetupPageResult:
    return GetSetupPageResult(
        yt_authentication_url="https://yt.example/auth",
        yt_credentials=None,
        tiktok_authentication_url="https://tt.example/auth",
        tiktok_credentials=None,
        is_completed=False,
    )


def _build_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.INSTAGRAM,
        status=IntegrationCheckStatus.OK,
        is_configured=True,
        is_publish_target=True,
        message="Instagram session verified.",
    )


def _build_instagram_not_configured_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.INSTAGRAM,
        status=IntegrationCheckStatus.NOT_CONFIGURED,
        is_configured=False,
        is_publish_target=True,
        message="Missing Instagram credentials or dependency.",
    )


def _build_instagram_verified_check_result() -> IntegrationCheckResult:
    return IntegrationCheckResult(
        platform=IntegrationPlatform.INSTAGRAM,
        status=IntegrationCheckStatus.OK,
        is_configured=True,
        is_publish_target=True,
        message="Instagram session verified.",
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
        login_response = _login_admin(client)

        dashboard_response = client.get("/admin")
        health_response = client.get("/admin/health/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert login_response.headers["location"] == "/admin"
    assert dashboard_response.status_code == 200
    assert "Data Connectors" in dashboard_response.text
    # Version is now loaded via HTMX from /admin/health/status
    assert health_response.status_code == 200
    assert f"v{get_app_version()}" in health_response.text


def test_admin_login_rejects_invalid_csrf(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        client.get("/admin/login")
        response = client.post(
            "/admin/login",
            data={"password": "admin-pass", "csrf_token": "invalid"},
            follow_redirects=False,
        )

    assert response.status_code == 403
    assert "Invalid or expired security token." in response.text


def test_admin_logout_revokes_captured_session(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = _login_admin(client)
        captured_session = client.cookies["session"]
        logout_response = client.post(
            "/admin/logout",
            data={"csrf_token": client.headers["X-CSRF-Token"]},
            follow_redirects=False,
        )
        client.cookies.set("session", captured_session)
        replay_response = client.get("/admin", follow_redirects=False)

    assert login_response.status_code == 303
    assert logout_response.status_code == 303
    assert replay_response.status_code == 303
    assert replay_response.headers["location"] == "/admin/login"


def test_admin_mutation_rejects_invalid_csrf(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = _login_admin(client)
        client.headers["X-CSRF-Token"] = "invalid"
        response = client.post("/admin/tasks/fetch/trigger")

    assert login_response.status_code == 303
    assert response.status_code == 403
    assert "Invalid CSRF token" in response.text


def test_admin_status_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.get("/admin/connections/status")

    assert response.status_code == 403
    assert 'id="admin-auth-error"' in response.text
    assert "Admin session expired or required." in response.text
    assert response.headers["hx-redirect"] == "/admin/login"


def test_admin_fragment_redirects_to_full_page_without_htmx(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = _login_admin(client)
        client.headers.pop("HX-Request", None)
        response = client.get("/admin/tasks/status", follow_redirects=False)

    assert login_response.status_code == 303
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_admin_fragment_returns_partial_with_htmx(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_admin_task_status_use_case] = lambda: _AdminTaskStatusUseCaseStub(
        TaskStatusResult(
            fetch_last_timestamp=None,
            daily_last_timestamp=None,
            weekly_last_timestamp=None,
            latest_status_by_method={},
            timeline_data={},
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/admin/tasks/status", headers={"HX-Request": "true"})

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert 'id="tasks-grid"' in response.text


def test_admin_status_returns_partial_when_authenticated(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        status_response = client.get("/admin/connections/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert status_response.status_code == 200
    assert "connections-grid" in status_response.text
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
        login_response = _login_admin(client)
        check_response = client.post("/admin/connections/instagram/check")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert check_response.status_code == 200
    assert "platform-card-instagram" in check_response.text
    assert 'hx-disabled-elt="this"' in check_response.text
    assert "VERIFIED" in check_response.text
    assert "Instagram session verified." in check_response.text
    rendered_label = next(label for label in ("Check publish", "Check connection") if label in check_response.text)
    assert check_response.text.rindex(rendered_label) < check_response.text.index("platform-card__check-spinner")


def test_admin_publisher_toggle_returns_single_publisher_card_fragment(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    publisher_state = _PublisherStateStub(
        enabled_by_slug={
            "youtube": True,
            "tiktok": True,
            "instagram": True,
        }
    )
    app.dependency_overrides[get_publisher_state_repo] = lambda: publisher_state
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        login_response = _login_admin(client)
        toggle_response = client.post("/admin/publishers/instagram/toggle")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert toggle_response.status_code == 200
    assert "publisher-card-instagram" in toggle_response.text
    assert "publishers-grid" not in toggle_response.text
    assert "publisher-card-tiktok" not in toggle_response.text


def test_admin_publisher_toggle_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.post("/admin/publishers/instagram/toggle")

    assert response.status_code == 403


def test_admin_publishers_status_shows_instagram_check_auth_button(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_publisher_state_repo] = lambda: _PublisherStateStub(
        enabled_by_slug={
            "youtube": True,
            "tiktok": True,
            "instagram": True,
        }
    )
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/admin/publishers/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert 'hx-post="/admin/publishers/instagram/check-auth"' in response.text
    assert "Check auth" in response.text


def test_admin_publisher_check_auth_returns_single_card_fragment(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_publisher_state_repo] = lambda: _PublisherStateStub(
        enabled_by_slug={
            "youtube": True,
            "tiktok": True,
            "instagram": True,
        }
    )
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()
    app.dependency_overrides[get_check_platform_connection_use_case] = lambda: _CheckPlatformConnectionUseCaseStub(
        _build_instagram_verified_check_result()
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/publishers/instagram/check-auth")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "publisher-card-instagram" in response.text
    assert "AUTH CHECK" in response.text
    assert "VERIFIED" in response.text
    assert "Instagram session verified." in response.text
    assert "publisher-card-youtube" not in response.text


def test_admin_publisher_toggle_returns_404_for_invalid_slug(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_publisher_state_repo] = lambda: _PublisherStateStub(enabled_by_slug={})
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/publishers/not-a-slug/toggle")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 404


def test_admin_health_status_returns_partial(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = _login_admin(client)
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
        login_response = _login_admin(client)
        response = client.get("/admin/metrics/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "metrics-grid" in response.text
    assert "FETCH" in response.text
    assert "COUNT" in response.text
    assert "ERROR RATE" in response.text


def test_admin_tasks_status_renders_retry_and_video_details(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_admin_task_status_use_case] = lambda: _AdminTaskStatusUseCaseStub(
        TaskStatusResult(
            fetch_last_timestamp=None,
            daily_last_timestamp=None,
            weekly_last_timestamp=None,
            latest_status_by_method={"daily": "failed"},
            latest_error_by_method={"daily": "challenge_required"},
            daily_publish_timestamps_by_platform={"YOUTUBE": (datetime.now(UTC) - timedelta(hours=2)).timestamp()},
            latest_video_artifact_path="videos/20260515/20260515_vertical_format.mp4",
            latest_video_artifact_timestamp=(datetime.now(UTC) - timedelta(hours=1)).timestamp(),
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/admin/tasks/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "Retry Daily" in response.text
    assert "Last Error:" in response.text
    assert "challenge_required" in response.text
    assert "Last processed video:" in response.text
    assert "Artifact path: videos/20260515/20260515_vertical_format.mp4" in response.text
    assert "Trigger Instagram" in response.text
    assert 'hx-post="/admin/tasks/daily/trigger?publisher=instagram"' in response.text


def test_admin_dashboard_renders_metrics_section(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())
    app.dependency_overrides[get_admin_task_status_use_case] = lambda: _AdminTaskStatusUseCaseStub(
        TaskStatusResult(
            fetch_last_timestamp=None,
            daily_last_timestamp=None,
            weekly_last_timestamp=None,
            latest_status_by_method={},
            timeline_data={},
        )
    )
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
    app.dependency_overrides[get_publisher_state_repo] = lambda: _PublisherStateStub(enabled_by_slug={})
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        login_response = _login_admin(client)
        dashboard_response = client.get("/admin")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert dashboard_response.status_code == 200
    assert "Runtime Metrics" in dashboard_response.text
    assert 'id="metrics-grid"' in dashboard_response.text
    assert 'id="tasks-grid"' in dashboard_response.text
    assert 'id="connectors-grid"' in dashboard_response.text
    assert 'id="publishers-grid"' in dashboard_response.text
    assert 'id="health-checks"' in dashboard_response.text


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
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/not-a-method/trigger")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 400
    assert "Invalid task method" in response.text
    assert 'id="tasks-feedback"' in response.text
    assert 'role="alert"' in response.text


def test_admin_task_trigger_returns_feedback_fragment_when_authenticated(monkeypatch) -> None:
    from src.entrypoints import fetch_data

    async def _fake_fetch_main_async(*, force_fetch: bool = False) -> bool:
        del force_fetch
        return True

    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setattr(fetch_data, "main_async", _fake_fetch_main_async)
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/fetch/trigger")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert 'id="tasks-feedback"' in response.text
    assert "Requested:" in response.text
    assert "Task &#39;fetch&#39; scheduled. Background execution will begin shortly." in response.text


def test_admin_task_trigger_records_failed_when_execution_lock_is_busy(monkeypatch) -> None:
    from src.entrypoints import fetch_data

    async def _busy_fetch_main_async(*, force_fetch: bool = False) -> bool:
        del force_fetch
        return False

    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setattr(fetch_data, "main_async", _busy_fetch_main_async)
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    trigger_stub = _TriggerAdminTaskUseCaseStub(completed_methods=[], failed_methods=[])
    app.dependency_overrides[get_trigger_admin_task_use_case] = lambda: trigger_stub

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/fetch/trigger")

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert trigger_stub.completed_methods == []
    assert trigger_stub.failed_methods == [
        ("fetch", "Task skipped because the execution lock is busy."),
    ]


def test_admin_task_trigger_force_fetch_query_param(monkeypatch) -> None:
    from src.entrypoints import fetch_data

    received_force: list[bool] = []

    async def _fake_fetch_main_async(*, force_fetch: bool = False) -> bool:
        received_force.append(force_fetch)
        return True

    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setattr(fetch_data, "main_async", _fake_fetch_main_async)
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/fetch/trigger?force=true")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert received_force == [True]


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
        login_response = _login_admin(client)
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


def test_admin_tasks_status_shows_running_indicator(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_admin_task_status_use_case] = lambda: _AdminTaskStatusUseCaseStub(
        TaskStatusResult(
            fetch_last_timestamp=None,
            daily_last_timestamp=None,
            weekly_last_timestamp=None,
            latest_status_by_method={"fetch": "queued"},
            running_methods={"fetch"},
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/admin/tasks/status")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "Running" in response.text
    assert "Task running" in response.text
    assert response.text.count('hx-disabled-elt="this"') >= 1


def test_admin_task_logs_requires_authenticated_session() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        response = client.get("/admin/tasks/logs/daily")

    assert response.status_code == 403


def test_admin_task_logs_returns_404_for_invalid_method(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/admin/tasks/logs/not-a-method")

    assert login_response.status_code == 303
    assert response.status_code == 404


def test_admin_task_trigger_daily_with_publisher_filter(monkeypatch) -> None:
    from src.entrypoints import publish_vertical

    received_targets: list[tuple[str, ...] | None] = []

    async def _fake_publish_vertical_main_async(*, target_publishers: tuple[str, ...] | None = None) -> bool:
        received_targets.append(target_publishers)
        return True

    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    monkeypatch.setattr(publish_vertical, "main_async", _fake_publish_vertical_main_async)
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/daily/trigger?publisher=instagram")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert received_targets == [("instagram",)]


def test_admin_task_trigger_daily_rejects_invalid_publisher(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/daily/trigger?publisher=invalid")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 400
    assert "Invalid publisher" in response.text
    assert 'id="tasks-feedback"' in response.text
    assert 'role="alert"' in response.text


def test_admin_task_trigger_fetch_rejects_publisher_filter(monkeypatch) -> None:
    monkeypatch.setenv("TOP_MUSIC_ADMIN_PASSWORD", "admin-pass")
    app = create_app(AppSettings(yt_search_region_code="ES", app_secret_key="session-secret"))
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(_build_setup_result())

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post("/admin/tasks/fetch/trigger?publisher=instagram")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 400
    assert "only supported for daily task" in response.text
