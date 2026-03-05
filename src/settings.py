"""
DEPRECATED: Import from src.config.settings instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.config.settings import AppSettings as AppSettings  # noqa: F401
from src.config.settings import Environment as Environment  # noqa: F401
from src.config.settings import get_app_settings as get_app_settings  # noqa: F401

warnings.warn(
    "src.settings is deprecated; use src.config.settings instead",
    DeprecationWarning,
    stacklevel=2,
)
