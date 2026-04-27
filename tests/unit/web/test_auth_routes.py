"""Unit tests for web auth routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.application.get_setup_page_use_case import GetSetupPageResult
from src.config.settings import AppSettings
from src.domain.models import SpotifyAuth, TikTokAuth, YtAuth
from src.web.dependencies import get_authorize_use_case, get_setup_page_use_case
from src.web.main import create_app

app = create_app(AppSettings(yt_search_region_code="ES"))


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

    async def execute_spotify(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="sp-client")


class _AuthorizeUseCaseSpotifyFailureStub(_AuthorizeUseCaseStub):
    async def execute_spotify(self, request: object) -> _AuthResponse:
        self.last_payload = request
        raise RuntimeError("spotify oauth exchange failed")


def test_retry_without_credentials_returns_403() -> None:
    with TestClient(app) as client:
        response = client.post("/retry/?method=fetch")

    assert response.status_code == 403
    assert response.json()["message"] == "Method fetch forbidden"


def test_yt_auth_with_code_redirects_to_root() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        response = client.get("/yt_auth/?code=abc", follow_redirects=False)

    app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"] == "/"
    assert use_case_stub.last_payload is not None


def test_yt_auth_without_code_redirects_to_root() -> None:
    app.dependency_overrides[get_authorize_use_case] = lambda: _AuthorizeUseCaseStub()

    with TestClient(app) as client:
        response = client.get("/yt_auth/", follow_redirects=False)

    app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"] == "/"


def test_spotify_auth_with_code_redirects_to_root() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        response = client.get("/spotify_auth/?code=abc", follow_redirects=False)

    app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"] == "/"
    assert use_case_stub.last_payload is not None


def test_spotify_auth_with_exchange_failure_redirects_to_setup() -> None:
    use_case_stub = _AuthorizeUseCaseSpotifyFailureStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        response = client.get("/spotify_auth/?code=abc", follow_redirects=False)

    app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"] == "/setup"


def test_setup_page_renders_viewmodel() -> None:
    setup_result = GetSetupPageResult(
        yt_authentication_url="https://yt.example/auth",
        yt_credentials=None,
        tiktok_authentication_url=None,
        tiktok_credentials=None,
        spotify_authentication_url="https://sp.example/auth",
        spotify_credentials=None,
        is_completed=False,
    )
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(setup_result)

    with TestClient(app) as client:
        response = client.get("/setup")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Top Video Generator" in response.text
    assert "Setup Platform Connections" in response.text
    assert "https://yt.example/auth" in response.text
    assert "https://sp.example/auth" in response.text
    assert "/tiktok_credentials/" in response.text


def test_tiktok_cookie_submission_redirects_to_setup() -> None:
    use_case_stub = _AuthorizeUseCaseStub()
    app.dependency_overrides[get_authorize_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        response = client.post(
            "/tiktok_credentials/",
            data={"tiktok_cookies": "cookie_payload"},
            follow_redirects=False,
        )

    app.dependency_overrides.clear()

    assert response.status_code == 303
    assert response.headers["location"] == "/setup"
    assert use_case_stub.last_payload is not None


def test_setup_page_redirects_when_completed() -> None:
    setup_result = GetSetupPageResult(
        yt_authentication_url=None,
        yt_credentials=YtAuth(client_id="yt-session"),
        tiktok_authentication_url=None,
        tiktok_credentials=TikTokAuth(client_id="tt-session"),
        spotify_authentication_url=None,
        spotify_credentials=SpotifyAuth(client_id="sp-session"),
        is_completed=True,
    )
    app.dependency_overrides[get_setup_page_use_case] = lambda: _SetupPageUseCaseStub(setup_result)

    with TestClient(app) as client:
        response = client.get("/setup", follow_redirects=False)

    app.dependency_overrides.clear()

    assert response.status_code == 307
    assert response.headers["location"] == "/"


class _SetupPageUseCaseStub:
    def __init__(self, result: GetSetupPageResult) -> None:
        self.result = result

    async def execute(self, _request: object) -> GetSetupPageResult:
        return self.result
