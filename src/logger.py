"""
DEPRECATED: Import from src.shared.logging instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.shared.logging import get_logger

__all__ = ["get_logger"]

warnings.warn(
    "src.logger is deprecated; use src.shared.logging instead",
    DeprecationWarning,
    stacklevel=2,
)
