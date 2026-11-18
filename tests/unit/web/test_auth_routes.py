"""Unit tests for web auth routes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.application.get_setup_page_use_case import GetSetupPageResult
from src.config.settings import AppSettings
from src.domain.models import TikTokAuth, YtAuth
from src.web.dependencies import get_authorize_use_case, get_setup_page_use_case
from src.web.main import create_app

app = create_app(
    AppSettings(
        env="development",
        yt_search_region_code="ES",
        app_secret_key="test-session-secret-with-at-least-32-characters",
        admin_password="admin-pass",
    )
)


def _login_admin(client: TestClient) -> object:
    login_page = client.get("/admin/login")
    match = re.search(r'name="csrf_token" value="([^"]+)"', login_page.text)
    assert match is not None
    csrf_token = match.group(1)
    client.headers["X-CSRF-Token"] = csrf_token
    return client.post(
        "/admin/login",
        data={"password": "admin-pass", "csrf_token": csrf_token},
        follow_redirects=False,
    )


@dataclass
class _AuthResponse:
    client_id: str


class _AuthorizeUseCaseStub:
    def __init__(self) -> None:
        self.last_payload: object | None = None

    async def execute_yt(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="yt-client")

    async def execute_tiktok_cookies(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="tt-client")


def test_yt_auth_with_code_redirects_to_root() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(
        GetSetupPageResult(
            yt_authentication_url="https://yt.example/auth",
            yt_credentials=None,
            tiktok_authentication_url=None,
            tiktok_credentials=None,
            is_completed=False,
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        setup_response = client.get("/setup")
        state_match = re.search(r"state=([A-Za-z0-9_-]+)", setup_response.text)
        assert state_match is not None
        response = client.get(
            f"/yt_auth/?code=abc&state={state_match.group(1)}",
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 307
    assert response.headers["location"] == "/"
    assert use_case_stub.last_payload is not None


def test_yt_auth_without_code_redirects_to_root() -> None:
    app.dependency_overrides[get_authorize_use_case] = lambda: _AuthorizeUseCaseStub()
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(
        GetSetupPageResult(
            yt_authentication_url="https://yt.example/auth",
            yt_credentials=None,
            tiktok_authentication_url=None,
            tiktok_credentials=None,
            is_completed=False,
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        setup_response = client.get("/setup")
        state_match = re.search(r"state=([A-Za-z0-9_-]+)", setup_response.text)
        assert state_match is not None
        response = client.get(
            f"/yt_auth/?state={state_match.group(1)}",
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 303
    assert response.headers["location"] == "/setup"


def test_yt_auth_requires_admin_session() -> None:
    with TestClient(app) as client:
        response = client.get("/yt_auth/?code=abc&state=unknown", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_yt_auth_rejects_state_mismatch() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(
        GetSetupPageResult(
            yt_authentication_url="https://yt.example/auth",
            yt_credentials=None,
            tiktok_authentication_url=None,
            tiktok_credentials=None,
            is_completed=False,
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        client.get("/setup")
        response = client.get(
            "/yt_auth/?code=abc&state=wrong-state",
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 303
    assert response.headers["location"] == "/setup"
    assert use_case_stub.last_payload is None


def test_setup_page_renders_viewmodel() -> None:
    setup_result = GetSetupPageResult(
        yt_authentication_url="https://yt.example/auth",
        yt_credentials=None,
        tiktok_authentication_url=None,
        tiktok_credentials=None,
        is_completed=False,
    )
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(setup_result)

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/setup")

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 200
    assert "Top Video Generator" in response.text
    assert "Setup Platform Connections" in response.text
    assert "https://yt.example/auth" in response.text
    assert "/tiktok_credentials/" in response.text
    assert 'for="tiktok-cookies"' in response.text
    assert 'id="tiktok-cookies"' in response.text


def test_tiktok_cookie_submission_redirects_to_setup() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(
        GetSetupPageResult(
            yt_authentication_url="https://yt.example/auth",
            yt_credentials=None,
            tiktok_authentication_url=None,
            tiktok_credentials=None,
            is_completed=False,
        )
    )

    with TestClient(app) as client:
        login_response = _login_admin(client)
        setup_page = client.get("/setup")
        match = re.search(r'name="csrf_token" value="([^"]+)"', setup_page.text)
        assert match is not None
        response = client.post(
            "/tiktok_credentials/",
            data={"tiktok_cookies": "cookie_payload", "csrf_token": match.group(1)},
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 303
    assert response.headers["location"] == "/setup"
    assert use_case_stub.last_payload is not None


def test_tiktok_cookie_submission_rejects_invalid_csrf() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.post(
            "/tiktok_credentials/",
            data={"tiktok_cookies": "cookie_payload", "csrf_token": "invalid"},
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 403
    assert use_case_stub.last_payload is None


def test_setup_requires_admin_session() -> None:
    with TestClient(app) as client:
        response = client.get("/setup", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_tiktok_cookie_submission_requires_admin_session() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/tiktok_credentials/",
            data={"tiktok_cookies": "cookie_payload", "csrf_token": "token"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_setup_page_redirects_when_completed() -> None:
    setup_result = GetSetupPageResult(
        yt_authentication_url=None,
        yt_credentials=YtAuth(client_id="yt-session"),
        tiktok_authentication_url=None,
        tiktok_credentials=TikTokAuth(client_id="tt-session"),
        is_completed=True,
    )
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(setup_result)

    with TestClient(app) as client:
        login_response = _login_admin(client)
        response = client.get("/setup", follow_redirects=False)

    app.dependency_overrides.clear()

    assert login_response.status_code == 303
    assert response.status_code == 307
    assert response.headers["location"] == "/"


class _SetupPageUseCaseStub:
    def __init__(self, result: GetSetupPageResult) -> None:
        self.result = result

    async def execute(self, _request: object) -> GetSetupPageResult:
        return self.result
