"""YouTube API client compatibility module.

Temporary bridge module during C3 migration. Canonical implementation
currently lives in src.infrastructure.youtube.client.
"""

from src.infrastructure.youtube.client import YTClient

__all__ = ["YTClient"]
