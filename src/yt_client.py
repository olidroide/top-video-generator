"""
DEPRECATED: Import from src.infrastructure.youtube instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.infrastructure.youtube import (
    MemoryCache as MemoryCache,
)
from src.infrastructure.youtube import (
    YTBase as YTBase,
)
from src.infrastructure.youtube import (
    YTClient as YTClient,
)
from src.infrastructure.youtube import (
    YTClientFake as YTClientFake,
)
from src.infrastructure.youtube import (
    YTClientT as YTClientT,
)
from src.infrastructure.youtube import (
    YTPageInfo as YTPageInfo,
)
from src.infrastructure.youtube import (
    YTRoot as YTRoot,
)
from src.infrastructure.youtube import (
    YTThumbnail as YTThumbnail,
)
from src.infrastructure.youtube import (
    YTVideContentStatistics as YTVideContentStatistics,
)
from src.infrastructure.youtube import (
    YTVideo as YTVideo,
)
from src.infrastructure.youtube import (
    YTVideoAgeGating as YTVideoAgeGating,
)
from src.infrastructure.youtube import (
    YTVideoContentDetails as YTVideoContentDetails,
)
from src.infrastructure.youtube import (
    YTVideoMonetizationDetails as YTVideoMonetizationDetails,
)
from src.infrastructure.youtube import (
    YTVideoMonetizationDetailsAccess as YTVideoMonetizationDetailsAccess,
)
from src.infrastructure.youtube import (
    YTVideoSnippet as YTVideoSnippet,
)
from src.infrastructure.youtube import (
    YTVideoSnippetLocalized as YTVideoSnippetLocalized,
)
from src.infrastructure.youtube import (
    YTVideoSnippetResource as YTVideoSnippetResource,
)
from src.infrastructure.youtube import (
    YTVideoSnippetThumbnail as YTVideoSnippetThumbnail,
)
from src.infrastructure.youtube import (
    YTVideoStatus as YTVideoStatus,
)
from src.infrastructure.youtube import (
    YTVideoTopicDetails as YTVideoTopicDetails,
)
from src.infrastructure.youtube import (
    YTVideoUploadRequest as YTVideoUploadRequest,
)
from src.infrastructure.youtube import (
    get_default_client as get_default_client,
)
from src.infrastructure.youtube import (
    get_yt_client as get_yt_client,
)

warnings.warn(
    "src.yt_client is deprecated; use src.infrastructure.youtube instead",
    DeprecationWarning,
    stacklevel=2,
)
