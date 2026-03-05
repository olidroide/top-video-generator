"""
DEPRECATED: Import from src.infrastructure.social.spotify_client instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.social.spotify_client import SpotifyClient as SpotifyClient  # noqa: F401

warnings.warn(
    "src.spotify_client is deprecated; use src.infrastructure.social.spotify_client instead",
    DeprecationWarning,
    stacklevel=2,
)
