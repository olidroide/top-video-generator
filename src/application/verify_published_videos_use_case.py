from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.domain.models import Platform, ReleaseKind, VideoVerificationResult, VideoVerificationStatus
from src.shared.logging import get_logger

if TYPE_CHECKING:
    from src.domain.ports import ReleaseStore, VideoVerifier

logger = get_logger(__name__)


@dataclass(frozen=True)
class VerificationReport:
    results: tuple[VideoVerificationResult, ...] = field(default_factory=tuple)
    verified_at: float | None = None


class VerifyPublishedVideosUseCase:
    def __init__(
        self,
        release_store: ReleaseStore,
        verifiers: list[VideoVerifier],
    ) -> None:
        self._release_store = release_store
        self._verifiers = {v.platform_name: v for v in verifiers}

    async def execute(self) -> VerificationReport:
        from datetime import UTC, datetime

        results: list[VideoVerificationResult] = []

        for platform in (Platform.YOUTUBE, Platform.INSTAGRAM):
            release = self._release_store.get_latest_release(
                platform=platform.value,
                release_kind=ReleaseKind.DAILY_VERTICAL.value,
            )
            if release is None or release.release_id is None:
                results.append(
                    VideoVerificationResult(
                        platform=platform.value,
                        status=VideoVerificationStatus.NOT_FOUND,
                        url="",
                        details="No release found",
                    )
                )
                continue

            verifier = self._verifiers.get(platform.value)
            if verifier is None:
                results.append(
                    VideoVerificationResult(
                        platform=platform.value,
                        status=VideoVerificationStatus.ERROR,
                        url="",
                        release_id=release.release_id,
                        details="No verifier available",
                    )
                )
                continue

            result = await verifier.verify(release.release_id)
            results.append(result)

        now = datetime.now(UTC).timestamp()
        logger.debug(
            "verification_report_generated",
            results_count=len(results),
            verified_at=now,
        )
        return VerificationReport(results=tuple(results), verified_at=now)
