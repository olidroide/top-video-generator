"""Unit tests for web page routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from src.application.fetch_top_videos_use_case import FetchTopVideosResult
from src.config.settings import AppSettings
from src.domain.models import Channel, Video
from src.web.dependencies import get_fetch_top_videos_use_case, get_release_repo
from src.web.main import create_app

app = create_app(AppSettings(yt_search_region_code="ES"))

if TYPE_CHECKING:
    import pytest


@dataclass
class _FetchTopVideosUseCaseStub:
    async def execute(self, _request: object) -> FetchTopVideosResult:
        video = Video(
            video_id="video-1",
            title="A Sample Song",
            channel=Channel(name="Channel A"),
            score=1,
            score_previous=2,
            views=1234,
            likes=98,
        )
        return FetchTopVideosResult(videos=(video,))


@dataclass
class _ReleaseRepoStub:
    def is_release_at_date(self, platform: str, release_date: object) -> bool:
        _ = (platform, release_date)
        return False


@dataclass
class _SettingsStub:
    yt_search_region_code: str | None = None


def test_index_renders_page_with_video_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.routes.pages.get_app_settings", lambda: _SettingsStub())
    app.dependency_overrides[get_fetch_top_videos_use_case] = lambda: _FetchTopVideosUseCaseStub()
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        response = client.get("/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "A Sample Song" in response.text
    assert "Channel A" in response.text
    assert "🌍 🔝 VIDEO GENERATOR" in response.text


def test_index_uses_globe_when_region_code_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.web.routes.pages.get_app_settings", lambda: _SettingsStub("WORLD"))
    app.dependency_overrides[get_fetch_top_videos_use_case] = lambda: _FetchTopVideosUseCaseStub()
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        response = client.get("/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "🌍 🔝 VIDEO GENERATOR" in response.text
