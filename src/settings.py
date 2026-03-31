"""
DEPRECATED: Import from src.config.settings instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.config.settings import AppSettings, Environment, get_app_settings

__all__ = ["AppSettings", "Environment", "get_app_settings"]

warnings.warn(
    "src.settings is deprecated; use src.config.settings instead",
    DeprecationWarning,
    stacklevel=2,
)
