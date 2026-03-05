"""
DEPRECATED: Import from src.infrastructure.social.instagram_client instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.social.instagram_client import InstagramClient as InstagramClient  # noqa: F401

warnings.warn(
    "src.instagram_client is deprecated; use src.infrastructure.social.instagram_client instead",
    DeprecationWarning,
    stacklevel=2,
)
