"""
DEPRECATED: Import from src.infrastructure.youtube.downloader instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.youtube.downloader import VideoDownloader

__all__ = ["VideoDownloader"]

warnings.warn(
    "src.video_downloader is deprecated; use src.infrastructure.youtube.downloader instead",
    DeprecationWarning,
    stacklevel=2,
)
