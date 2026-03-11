"""YouTube auth manager compatibility module.

Temporary bridge module during C3 migration. Canonical implementation
currently lives in src.infrastructure.youtube.client.
"""

from src.infrastructure.youtube.client import MemoryCache

__all__ = ["MemoryCache"]
