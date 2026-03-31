"""
DEPRECATED: Import from src.infrastructure.youtube instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.youtube import (
    MemoryCache,
    YTBase,
    YTClient,
    YTClientFake,
    YTClientT,
    YTPageInfo,
    YTRoot,
    YTThumbnail,
    YTVideContentStatistics,
    YTVideo,
    YTVideoAgeGating,
    YTVideoContentDetails,
    YTVideoMonetizationDetails,
    YTVideoMonetizationDetailsAccess,
    YTVideoSnippet,
    YTVideoSnippetLocalized,
    YTVideoSnippetResource,
    YTVideoSnippetThumbnail,
    YTVideoStatus,
    YTVideoTopicDetails,
    YTVideoUploadRequest,
    get_default_client,
    get_yt_client,
)

__all__ = [
    "MemoryCache",
    "YTBase",
    "YTClient",
    "YTClientFake",
    "YTClientT",
    "YTPageInfo",
    "YTRoot",
    "YTThumbnail",
    "YTVideContentStatistics",
    "YTVideo",
    "YTVideoAgeGating",
    "YTVideoContentDetails",
    "YTVideoMonetizationDetails",
    "YTVideoMonetizationDetailsAccess",
    "YTVideoSnippet",
    "YTVideoSnippetLocalized",
    "YTVideoSnippetResource",
    "YTVideoSnippetThumbnail",
    "YTVideoStatus",
    "YTVideoTopicDetails",
    "YTVideoUploadRequest",
    "get_default_client",
    "get_yt_client",
]

warnings.warn(
    "src.yt_client is deprecated; use src.infrastructure.youtube instead",
    DeprecationWarning,
    stacklevel=2,
)
