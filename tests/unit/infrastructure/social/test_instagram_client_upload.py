from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.infrastructure.social import instagram_client as instagram_client_module
from src.infrastructure.social.instagram_client import InstagramClient


@pytest.mark.asyncio
async def test_upload_video_retries_transient_clip_configure_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = InstagramClient()
    calls = {"count": 0}

    def _fake_upload_once(video_path: str, caption: str) -> SimpleNamespace:
        _ = video_path, caption
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("configure_to_clips too many 500 error responses")
        return SimpleNamespace(pk="123")

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(client, "_upload_with_normal_client", _fake_upload_once)
    monkeypatch.setattr(instagram_client_module.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(instagram_client_module.asyncio, "sleep", _fake_sleep)

    media_id = await client.upload_video("videos/20260612/20260612_vertical_format.mp4", "caption")

    assert media_id == "123"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_upload_video_does_not_retry_non_transient_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = InstagramClient()
    calls = {"count": 0}

    def _fake_upload_once(video_path: str, caption: str) -> SimpleNamespace:
        _ = video_path, caption
        calls["count"] += 1
        raise RuntimeError("permission denied")

    async def _fake_to_thread(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(client, "_upload_with_normal_client", _fake_upload_once)
    monkeypatch.setattr(instagram_client_module.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(instagram_client_module.asyncio, "sleep", _fake_sleep)

    media_id = await client.upload_video("videos/20260612/20260612_vertical_format.mp4", "caption")

    assert media_id is None
    assert calls["count"] == 1


def test_is_clip_configure_transient_error_detects_expected_patterns() -> None:
    assert InstagramClient._is_clip_configure_transient_error(
        RuntimeError("configure_to_clips too many 500 error responses")
    )
    assert InstagramClient._is_clip_configure_transient_error(RuntimeError("Transcode not finished yet"))
    assert not InstagramClient._is_clip_configure_transient_error(RuntimeError("permission denied"))


def test_upload_with_normal_client_passes_configure_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, int] = {}

    class _FakeClient:
        def clip_upload(self, **kwargs):
            called.update(kwargs)
            return SimpleNamespace(pk="123")

    monkeypatch.setattr(instagram_client_module, "_get_instagram_client", lambda: _FakeClient())

    media = InstagramClient._upload_with_normal_client("videos/20260612/20260612_vertical_format.mp4", "caption")

    assert media.pk == "123"
    assert called["configure_timeout"] == InstagramClient._CLIP_CONFIGURE_TIMEOUT_SECONDS
