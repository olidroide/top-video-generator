from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.domain.ports import IntegrationChecker


@dataclass(frozen=True)
class CheckPlatformConnectionRequest:
    """Request payload for checking a single external integration."""

    platform: IntegrationPlatform


class CheckPlatformConnectionUseCase:
    """Run a live connectivity check for a single platform."""

    def __init__(self, checkers: Sequence[IntegrationChecker]) -> None:
        self._checkers = checkers

    async def execute(self, request: CheckPlatformConnectionRequest) -> IntegrationCheckResult:
        for checker in self._checkers:
            if checker.platform_name == request.platform:
                return await checker.check_connection()

        return IntegrationCheckResult(
            platform=request.platform,
            status=IntegrationCheckStatus.ERROR,
            is_configured=False,
            is_publish_target=False,
            message="No checker registered for this platform.",
        )
