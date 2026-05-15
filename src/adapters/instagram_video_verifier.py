from __future__ import annotations

from src.domain.models import VideoVerificationResult, VideoVerificationStatus
from src.infrastructure.social.instagram_client import (
    InstagramClient,
    InstagramDependencyError,
    InstagramLoginError,
)


class InstagramVideoVerifier:
    @property
    def platform_name(self) -> str:
        return "INSTAGRAM"

    async def verify(self, release_id: str) -> VideoVerificationResult:
        url = f"https://www.instagram.com/reel/{release_id}/"
        try:
            client = InstagramClient()
            media_info = await client.get_media_info(release_id)
            if media_info:
                return VideoVerificationResult(
                    platform=self.platform_name,
                    status=VideoVerificationStatus.LIVE,
                    url=url,
                    release_id=release_id,
                    title=getattr(media_info, "caption_text", None),
                )
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.NOT_FOUND,
                url=url,
                release_id=release_id,
                details="Media not found",
            )
        except InstagramLoginError as exc:
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.ERROR,
                url=url,
                release_id=release_id,
                details=f"Auth failed: {exc}",
            )
        except InstagramDependencyError:
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.ERROR,
                url=url,
                release_id=release_id,
                details="instagrapi not installed",
            )
        except Exception as exc:  # noqa: BLE001
            return VideoVerificationResult(
                platform=self.platform_name,
                status=VideoVerificationStatus.ERROR,
                url=url,
                release_id=release_id,
                details=str(exc),
            )
