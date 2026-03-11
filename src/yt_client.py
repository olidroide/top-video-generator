"""
DEPRECATED: Import from src.infrastructure.youtube.client instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.youtube.client import MemoryCache as MemoryCache  # noqa: F401
from src.infrastructure.youtube.client import YTBase as YTBase  # noqa: F401
from src.infrastructure.youtube.client import YTClient as YTClient  # noqa: F401
from src.infrastructure.youtube.client import YTClientFake as YTClientFake  # noqa: F401
from src.infrastructure.youtube.client import YTClientT as YTClientT  # noqa: F401
from src.infrastructure.youtube.client import YTPageInfo as YTPageInfo  # noqa: F401
from src.infrastructure.youtube.client import YTRoot as YTRoot  # noqa: F401
from src.infrastructure.youtube.client import YTThumbnail as YTThumbnail  # noqa: F401
from src.infrastructure.youtube.client import YTVideo as YTVideo  # noqa: F401
from src.infrastructure.youtube.client import YTVideoAgeGating as YTVideoAgeGating  # noqa: F401
from src.infrastructure.youtube.client import YTVideoContentDetails as YTVideoContentDetails  # noqa: F401
from src.infrastructure.youtube.client import YTVideoMonetizationDetails as YTVideoMonetizationDetails  # noqa: F401
from src.infrastructure.youtube.client import (
    YTVideoMonetizationDetailsAccess as YTVideoMonetizationDetailsAccess,
)  # noqa: F401
from src.infrastructure.youtube.client import YTVideoSnippet as YTVideoSnippet  # noqa: F401
from src.infrastructure.youtube.client import YTVideoSnippetLocalized as YTVideoSnippetLocalized  # noqa: F401
from src.infrastructure.youtube.client import YTVideoSnippetResource as YTVideoSnippetResource  # noqa: F401
from src.infrastructure.youtube.client import YTVideoSnippetThumbnail as YTVideoSnippetThumbnail  # noqa: F401
from src.infrastructure.youtube.client import YTVideoStatus as YTVideoStatus  # noqa: F401
from src.infrastructure.youtube.client import YTVideoTopicDetails as YTVideoTopicDetails  # noqa: F401
from src.infrastructure.youtube.client import YTVideoUploadRequest as YTVideoUploadRequest  # noqa: F401
from src.infrastructure.youtube.client import YTVideContentStatistics as YTVideContentStatistics  # noqa: F401
from src.infrastructure.youtube.client import get_default_client as get_default_client  # noqa: F401
from src.infrastructure.youtube.client import get_yt_client as get_yt_client  # noqa: F401

warnings.warn(
    "src.yt_client is deprecated; use src.infrastructure.youtube.client instead",
    DeprecationWarning,
    stacklevel=2,
)
