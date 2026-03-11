"""YouTube infrastructure integration."""

from src.infrastructure.youtube.auth_manager import MemoryCache, get_default_client
from src.infrastructure.youtube.client import YTClient, YTClientFake, YTClientT, get_yt_client
from src.infrastructure.youtube.schemas import (
    YTBase,
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
    "YTVideo",
    "YTVideoAgeGating",
    "YTVideoContentDetails",
    "YTVideContentStatistics",
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
