from __future__ import annotations

from unittest.mock import AsyncMock, create_autospec

from src.application.check_platform_connection_use_case import (
    CheckPlatformConnectionRequest,
    CheckPlatformConnectionUseCase,
)
from src.domain.models import IntegrationCheckResult, IntegrationCheckStatus, IntegrationPlatform
from src.domain.ports import IntegrationChecker


async def test_check_platform_connection_use_case_returns_checker_result() -> None:
    checker = create_autospec(IntegrationChecker, instance=True)
    checker.platform_name = IntegrationPlatform.SPOTIFY
    checker.check_connection = AsyncMock(
        return_value=IntegrationCheckResult(
            platform=IntegrationPlatform.SPOTIFY,
            status=IntegrationCheckStatus.OK,
            is_configured=True,
            is_publish_target=False,
            message="Spotify account access verified.",
        )
    )
    use_case = CheckPlatformConnectionUseCase(checkers=[checker])

    result = await use_case.execute(CheckPlatformConnectionRequest(platform=IntegrationPlatform.SPOTIFY))

    assert result.platform == IntegrationPlatform.SPOTIFY
    assert result.status == IntegrationCheckStatus.OK
    checker.check_connection.assert_awaited_once()


async def test_check_platform_connection_use_case_returns_error_when_checker_missing() -> None:
    use_case = CheckPlatformConnectionUseCase(checkers=[])

    result = await use_case.execute(CheckPlatformConnectionRequest(platform=IntegrationPlatform.YOUTUBE))

    assert result.platform == IntegrationPlatform.YOUTUBE
    assert result.status == IntegrationCheckStatus.ERROR
    assert result.message == "No checker registered for this platform."


async def test_check_platform_connection_use_case_returns_error_when_checker_raises() -> None:
    checker = create_autospec(IntegrationChecker, instance=True)
    checker.platform_name = IntegrationPlatform.YOUTUBE
    checker.check_connection = AsyncMock(side_effect=RuntimeError("boom"))
    use_case = CheckPlatformConnectionUseCase(checkers=[checker])

    result = await use_case.execute(CheckPlatformConnectionRequest(platform=IntegrationPlatform.YOUTUBE))

    assert result.platform == IntegrationPlatform.YOUTUBE
    assert result.status == IntegrationCheckStatus.ERROR
    assert result.is_configured is False
    assert result.is_publish_target is False
    assert result.message == "Unexpected checker failure: boom"
    checker.check_connection.assert_awaited_once()
