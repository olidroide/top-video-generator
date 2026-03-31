"""Unit tests for web auth routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.web.dependencies import get_authorize_use_case
from src.web.main import app


@dataclass
class _AuthResponse:
    client_id: str


class _AuthorizeUseCaseStub:
    def __init__(self) -> None:
        self.last_payload: object | None = None

    async def execute_yt(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="yt-client")

    async def execute_tiktok(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="tt-client")

    async def execute_spotify(self, request: object) -> _AuthResponse:
        self.last_payload = request
        return _AuthResponse(client_id="sp-client")


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
