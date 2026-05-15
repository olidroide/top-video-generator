from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.models import Release, VideoVerificationResult, VideoVerificationStatus
from src.domain.ports import VideoVerifier


class FakeVerifier(VideoVerifier):
    def __init__(self, platform: str, result: VideoVerificationResult) -> None:
        self._platform = platform
        self._result = result

    @property
    def platform_name(self) -> str:
        return self._platform

    async def verify(self, release_id: str) -> VideoVerificationResult:  # noqa: ARG002
        return self._result


@pytest.mark.asyncio
async def test_verify_both_platforms() -> None:
    release_store = MagicMock()
    release_store.get_latest_release.side_effect = lambda platform, release_kind: Release(
        platform=platform,
        release_kind=release_kind,
        release_id=f"id_{platform.lower()}",
        published_at=1234567890.0,
    )

    yt_result = VideoVerificationResult(
        platform="YOUTUBE",
        status=VideoVerificationStatus.LIVE,
        url="https://youtube.com/watch?v=yt",
        release_id="id_youtube",
    )
    ig_result = VideoVerificationResult(
        platform="INSTAGRAM",
        status=VideoVerificationStatus.LIVE,
        url="https://instagram.com/reel/ig",
        release_id="id_instagram",
    )

    verifiers = [
        FakeVerifier("YOUTUBE", yt_result),
        FakeVerifier("INSTAGRAM", ig_result),
    ]

    from src.application.verify_published_videos_use_case import VerifyPublishedVideosUseCase

    use_case = VerifyPublishedVideosUseCase(release_store=release_store, verifiers=verifiers)
    report = await use_case.execute()

    assert len(report.results) == 2
    assert report.verified_at is not None
    assert all(r.status == VideoVerificationStatus.LIVE for r in report.results)


@pytest.mark.asyncio
async def test_verify_missing_release() -> None:
    release_store = MagicMock()
    release_store.get_latest_release.return_value = None

    verifiers: list[VideoVerifier] = []

    from src.application.verify_published_videos_use_case import VerifyPublishedVideosUseCase

    use_case = VerifyPublishedVideosUseCase(release_store=release_store, verifiers=verifiers)
    report = await use_case.execute()

    assert len(report.results) == 2
    assert all(r.status == VideoVerificationStatus.NOT_FOUND for r in report.results)
    assert all(r.details == "No release found" for r in report.results)


@pytest.mark.asyncio
async def test_verify_missing_verifier() -> None:
    release_store = MagicMock()
    release_store.get_latest_release.side_effect = lambda platform, release_kind: Release(
        platform=platform,
        release_kind=release_kind,
        release_id=f"id_{platform.lower()}",
        published_at=1234567890.0,
    )

    from src.application.verify_published_videos_use_case import VerifyPublishedVideosUseCase

    use_case = VerifyPublishedVideosUseCase(release_store=release_store, verifiers=[])
    report = await use_case.execute()

    assert len(report.results) == 2
    assert all(r.status == VideoVerificationStatus.ERROR for r in report.results)
    assert all(r.details == "No verifier available" for r in report.results)


@pytest.mark.asyncio
async def test_verify_missing_release_id() -> None:
    release_store = MagicMock()
    release_store.get_latest_release.side_effect = lambda platform, release_kind: Release(
        platform=platform,
        release_kind=release_kind,
        release_id=None,
        published_at=1234567890.0,
    )

    from src.application.verify_published_videos_use_case import VerifyPublishedVideosUseCase

    use_case = VerifyPublishedVideosUseCase(release_store=release_store, verifiers=[])
    report = await use_case.execute()

    assert len(report.results) == 2
    assert all(r.status == VideoVerificationStatus.NOT_FOUND for r in report.results)
