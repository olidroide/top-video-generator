from __future__ import annotations

from src.config.settings import get_app_settings
from src.domain.models import VideoVerificationResult, VideoVerificationStatus
from src.infrastructure.youtube.yt_client import YTClient
from src.infrastructure.youtube.yt_fake_client import YTClientFake


def _build_yt_client() -> YTClient:
    settings = get_app_settings()
    return YTClient() if settings.is_production_env else YTClientFake()


class YouTubeVideoVerifier:
    @property
    def platform_name(self) -> str:
        return "YOUTUBE"

    async def verify(self, release_id: str) -> VideoVerificationResult:
        url = f"https://www.youtube.com/watch?v={release_id}"
        try:
            client = _build_yt_client()
            details = await client.get_video_details(release_id)
            if not details.items:
                return VideoVerificationResult(
                    platform=self.platform_name,
                    status=VideoVerificationStatus.NOT_FOUND,
                    url=url,
                    release_id=release_id,
                    details="Video not found in YouTube API",
                )
            video = details.items[0]
            status = video.status
            if status and status.upload_status == "processed" and status.privacy_status == "public":
                return VideoVerificationResult(
                    platform=self.platform_name,
                    status=VideoVerificationStatus.LIVE,
                    url=url,
                    release_id=release_id,
                    title=video.snippet.title if video.snippet else None,
                    details=f"Privacy: {status.privacy_status}",
                )
            upload_status = status.upload_status if status else "unknown"
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.PROCESSING,
                url=url,
                release_id=release_id,
                title=video.snippet.title if video.snippet else None,
                details=f"Upload status: {upload_status}",
            )
        except Exception as exc:  # noqa: BLE001
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.ERROR,
                url=url,
                release_id=release_id,
                details=str(exc),
            )
