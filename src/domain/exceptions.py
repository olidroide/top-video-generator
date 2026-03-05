"""Domain layer exceptions."""

from __future__ import annotations


class DomainError(Exception):
    """Base exception for all domain errors."""


class FetchError(DomainError):
    """Raised when fetching trending videos fails."""

    def __init__(self, region: str, cause: Exception) -> None:
        super().__init__(f"Failed to fetch trending videos for region={region!r}")
        self.region = region
        self.__cause__ = cause


class PublishError(DomainError):
    """Raised when publishing to a platform fails unrecoverably."""

    def __init__(self, platform: str, cause: Exception) -> None:
        super().__init__(f"Failed to publish to platform={platform!r}")
        self.platform = platform
        self.__cause__ = cause


class ScoringError(DomainError):
    """Raised when the scoring pipeline has insufficient data."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Cannot score video list: {reason}")
