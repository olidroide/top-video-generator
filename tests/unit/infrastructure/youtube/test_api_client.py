from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.infrastructure.youtube.yt_client import YTClient


class _FakeRequest:
    def __init__(self, result: dict[str, object], calls: list[dict[str, object]]) -> None:
        self._result = result
        self._calls = calls

    def execute(self) -> dict[str, object]:
        self._calls.append(self._result)
        return self._result


class _FakeVideosResource:
    def __init__(self, result: dict[str, object], calls: dict[str, object]) -> None:
        self._result = result
        self._calls = calls

    def insert(self, **kwargs: object) -> _FakeRequest:
        self._calls["videos.insert"] = kwargs
        return _FakeRequest(self._result, self._calls.setdefault("executions", []))


class _FakeThumbnailsResource:
    def __init__(self, calls: dict[str, object]) -> None:
        self._calls = calls

    def set(self, **kwargs: object) -> _FakeRequest:
        self._calls["thumbnails.set"] = kwargs
        return _FakeRequest({}, self._calls.setdefault("executions", []))


class _FakePlaylistItemsResource:
    def __init__(self, calls: dict[str, object]) -> None:
        self._calls = calls

    def insert(self, **kwargs: object) -> _FakeRequest:
        self._calls["playlistItems.insert"] = kwargs
        return _FakeRequest({}, self._calls.setdefault("executions", []))


class _FakeYouTubeService:
    def __init__(self) -> None:
        self.calls: dict[str, object] = {}
        self._videos = _FakeVideosResource({"id": "published-id"}, self.calls)
        self._thumbnails = _FakeThumbnailsResource(self.calls)
        self._playlist_items = _FakePlaylistItemsResource(self.calls)

    def videos(self) -> _FakeVideosResource:
        return self._videos

    def thumbnails(self) -> _FakeThumbnailsResource:
        return self._thumbnails

    def playlistItems(self) -> _FakePlaylistItemsResource:  # noqa: N802
        return self._playlist_items


class _FakeMediaFileUpload:
    def __init__(self, path: str, *, chunksize: int | None = None, resumable: bool | None = None) -> None:
        self.path = path
        self.chunksize = chunksize
        self.resumable = resumable


@pytest.mark.asyncio
async def test_yt_client_upload_video_builds_expected_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    service = _FakeYouTubeService()
    client = YTClient.__new__(YTClient)
    client.get_authenticated_service = lambda: service
    client._yt_search_language_code = "es"
    client._yt_search_region_code = "ES"
    client._yt_search_category_code = "10"
    client._yt_tags = ["tag1", "@@YEAR@@", "tag3"]

    async def _to_thread(func: object, /, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)  # type: ignore[misc]

    monkeypatch.setattr("src.infrastructure.youtube.yt_client.asyncio.to_thread", _to_thread)
    monkeypatch.setattr("src.infrastructure.youtube.yt_client.MediaFileUpload", _FakeMediaFileUpload)

    result = await YTClient.upload_video(
        client,
        video_path="/tmp/video.mp4",
        title="A" * 120,
        description="B" * 5000,
        thumbnail_path="/tmp/thumb.png",
        playlist_id="playlist-1",
        tags=["#custom", "other"],
    )

    assert result == "published-id"

    insert_kwargs = service.calls["videos.insert"]
    body = insert_kwargs["body"]
    assert body["snippet"]["title"] == "A" * 95
    assert body["snippet"]["description"] == "B" * 4900
    assert body["snippet"]["categoryId"] == "10"
    assert body["snippet"]["defaultAudioLanguage"] == "es"
    assert body["snippet"]["tags"] == ["tag1", "2026", "tag3", "custom", "other"]

    assert service.calls["thumbnails.set"]["videoId"] == "published-id"
    assert service.calls["playlistItems.insert"]["body"]["snippet"]["playlistId"] == "playlist-1"


@pytest.mark.asyncio
async def test_upload_video_returns_none_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingRequest:
        def execute(self) -> dict[str, object]:
            from googleapiclient.errors import HttpError

            raise HttpError(resp=SimpleNamespace(status=500, reason="boom"), content=b"boom")

    class _FailingService(_FakeYouTubeService):
        def videos(self) -> _FakeVideosResource:
            class _FailingVideosResource(_FakeVideosResource):
                def insert(self, **kwargs: object) -> _FailingRequest:
                    self._calls["videos.insert"] = kwargs
                    return _FailingRequest()

            return _FailingVideosResource({"id": "unused"}, self.calls)

    service = _FailingService()
    client = YTClient.__new__(YTClient)
    client.get_authenticated_service = lambda: service
    client._yt_search_language_code = "es"
    client._yt_search_region_code = "ES"
    client._yt_search_category_code = "10"
    client._yt_tags = []

    async def _to_thread(func: object, /, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)  # type: ignore[misc]

    monkeypatch.setattr("src.infrastructure.youtube.yt_client.asyncio.to_thread", _to_thread)
    monkeypatch.setattr("src.infrastructure.youtube.yt_client.MediaFileUpload", _FakeMediaFileUpload)

    result = await YTClient.upload_video(
        client,
        video_path="/tmp/video.mp4",
        title="Title",
        description="Description",
    )

    assert result is None
