"""Unit tests for web page routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from src.application.fetch_top_videos_use_case import FetchTopVideosResult
from src.domain.models import Channel, Video
from src.web.dependencies import get_fetch_top_videos_use_case, get_release_repo
from src.web.main import app


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


def test_index_renders_page_with_video_list() -> None:
    app.dependency_overrides[get_fetch_top_videos_use_case] = lambda: _FetchTopVideosUseCaseStub()
    app.dependency_overrides[get_release_repo] = lambda: _ReleaseRepoStub()

    with TestClient(app) as client:
        response = client.get("/")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "A Sample Song" in response.text
    assert "Channel A" in response.text
