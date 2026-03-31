"""
DEPRECATED: Import from src.infrastructure.social.tiktok_client instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.social.tiktok_client import TikTokClient

__all__ = ["TikTokClient"]

warnings.warn(
    "src.tiktok_client is deprecated; use src.infrastructure.social.tiktok_client instead",
    DeprecationWarning,
    stacklevel=2,
)
