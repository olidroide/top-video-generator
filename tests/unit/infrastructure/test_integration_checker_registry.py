from __future__ import annotations

from src.domain.models import IntegrationPlatform


class _FakeChecker:
    def __init__(self, platform_name: IntegrationPlatform) -> None:
        self._platform_name = platform_name

    @property
    def platform_name(self) -> IntegrationPlatform:
        return self._platform_name

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def is_publish_target(self) -> bool:
        return True

    async def check_connection(self):  # pragma: no cover - not used here
        raise NotImplementedError


def test_build_integration_checkers_returns_all_platforms(monkeypatch) -> None:
    from src.infrastructure import integration_checker_registry

    monkeypatch.setattr(
        integration_checker_registry,
        "InstagramIntegrationChecker",
        lambda: _FakeChecker(IntegrationPlatform.INSTAGRAM),
    )
    monkeypatch.setattr(
        integration_checker_registry,
        "TikTokIntegrationChecker",
        lambda: _FakeChecker(IntegrationPlatform.TIKTOK),
    )
    monkeypatch.setattr(
        integration_checker_registry,
        "YouTubeIntegrationChecker",
        lambda: _FakeChecker(IntegrationPlatform.YOUTUBE),
    )

    result = integration_checker_registry.build_integration_checkers()

    assert [checker.platform_name for checker in result] == [
        IntegrationPlatform.INSTAGRAM,
        IntegrationPlatform.TIKTOK,
        IntegrationPlatform.YOUTUBE,
    ]
