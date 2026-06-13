from __future__ import annotations

from pathlib import Path
from typing import Self

import pytest

from src.config.settings import AppSettings, Environment
from src.domain.models import Video
from src.infrastructure.video.downloader import VideoDownloader


def _make_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        env=Environment.DEVELOPMENT,
        yt_search_region_code="ES",
        video_generated_folder=str(tmp_path),
    )


def test_init_creates_download_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr("src.infrastructure.video.downloader.get_app_settings", lambda: settings)

    downloader = VideoDownloader()

    expected_folder = tmp_path / "yt"
    assert downloader.video_yt_resources_folder == str(expected_folder)
    assert expected_folder.is_dir()


@pytest.mark.asyncio
async def test_download_video_uses_separate_options_for_long_and_short_videos(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr("src.infrastructure.video.downloader.get_app_settings", lambda: settings)

    created_options: list[dict[str, object]] = []
    download_calls: list[list[str]] = []

    class _FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            created_options.append(options)
            self._output_template = str(options["outtmpl"])

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def download(self, urls: list[str]) -> None:
            download_calls.append(list(urls))
            for url in urls:
                video_id = url.split("v=")[-1]
                output_path = Path(self._output_template.replace("%(id)s", video_id).replace("%(ext)s", "mp4"))
                output_path.touch()

    monkeypatch.setattr("src.infrastructure.video.downloader.YoutubeDL", _FakeYoutubeDL)

    downloader = VideoDownloader()
    video_list = [
        Video(video_id="long-video", duration=61),
        Video(video_id="short-video", duration=60),
    ]

    await downloader.download_video(video_list)

    assert download_calls == [[video_list[0].yt_video_url], [video_list[1].yt_video_url]]
    assert len(created_options) == 2
    assert "download_ranges" in created_options[0]
    assert "download_ranges" not in created_options[1]


def test_is_already_downloaded_accepts_non_mp4_assets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr("src.infrastructure.video.downloader.get_app_settings", lambda: settings)

    downloader = VideoDownloader()
    (tmp_path / "yt" / "video-1.webm").touch()

    assert downloader.is_already_downloaded(Video(video_id="video-1", duration=30)) is True


@pytest.mark.asyncio
async def test_download_video_raises_when_assets_are_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = _make_settings(tmp_path)
    monkeypatch.setattr("src.infrastructure.video.downloader.get_app_settings", lambda: settings)

    class _FakeYoutubeDL:
        def __init__(self, _options: dict[str, object]) -> None:
            return

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        def download(self, _urls: list[str]) -> None:
            return

    monkeypatch.setattr("src.infrastructure.video.downloader.YoutubeDL", _FakeYoutubeDL)

    downloader = VideoDownloader()
    video = Video(video_id="missing-video", duration=61)

    with pytest.raises(RuntimeError, match="Missing downloaded assets for video IDs: missing-video"):
        await downloader.download_video([video])
