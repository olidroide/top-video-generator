"""Unit tests for web page routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, create_autospec

from fastapi.testclient import TestClient

from src.application.get_top_videos_dashboard_use_case import GetTopVideosDashboardResult, GetTopVideosDashboardUseCase
from src.config.settings import AppSettings
from src.domain.models import Channel, Video
from src.web.dependencies import get_top_videos_dashboard_use_case
from src.web.main import create_app


def _build_dashboard_use_case_stub() -> GetTopVideosDashboardUseCase:
    mock_use_case = create_autospec(GetTopVideosDashboardUseCase, instance=True)
    video = Video(
        video_id="video-1",
        title="A Sample Song",
        channel=Channel(name="Channel A"),
        score=1,
        score_previous=2,
        views=1234,
        likes=98,
    )
    mock_use_case.execute = AsyncMock(
        return_value=GetTopVideosDashboardResult(videos=(video,), yt_video_published=False)
    )
    return mock_use_case


def test_index_renders_page_with_video_list() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES"))
    app.dependency_overrides[get_top_videos_dashboard_use_case] = _build_dashboard_use_case_stub

    with TestClient(app) as client:
        response = client.get("/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "A Sample Song" in response.text
    assert "Channel A" in response.text
    assert "🇪🇸 🔝 VIDEO GENERATOR" in response.text


def test_index_uses_globe_when_region_code_is_invalid() -> None:
    app = create_app(AppSettings(yt_search_region_code="WORLD"))
    app.dependency_overrides[get_top_videos_dashboard_use_case] = _build_dashboard_use_case_stub

    with TestClient(app) as client:
        response = client.get("/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "🌍 🔝 VIDEO GENERATOR" in response.text


def test_index_uses_requested_daily_query_param() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES"))

    class _CaptureDashboardUseCase:
        def __init__(self) -> None:
            self.last_request = None

        async def execute(self, request: object) -> GetTopVideosDashboardResult:
            self.last_request = request
            return GetTopVideosDashboardResult(videos=(), yt_video_published=False)

    use_case_stub = _CaptureDashboardUseCase()
    app.dependency_overrides[get_top_videos_dashboard_use_case] = lambda: use_case_stub

    with TestClient(app) as client:
        response = client.get("/?daily=2026-03-31")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "?daily=2026-03-31" in response.text
    assert use_case_stub.last_request is not None
    assert getattr(use_case_stub.last_request, "day", None).isoformat() == "2026-03-31"


def test_index_rejects_daily_query_before_minimum_date() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES"))
    app.dependency_overrides[get_top_videos_dashboard_use_case] = _build_dashboard_use_case_stub

    with TestClient(app) as client:
        response = client.get("/?daily=2019-12-31")

    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Daily date out of range"


def test_index_hides_previous_navigation_at_minimum_daily_date() -> None:
    app = create_app(AppSettings(yt_search_region_code="ES"))
    app.dependency_overrides[get_top_videos_dashboard_use_case] = _build_dashboard_use_case_stub

    with TestClient(app) as client:
        response = client.get("/?daily=2020-01-01")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "?daily=2019-12-31" not in response.text
