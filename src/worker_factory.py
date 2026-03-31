"""
DEPRECATED: Import from src.application.workers.factory instead.

This module is a temporary shim for backward compatibility.
Scheduled for removal after all imports are migrated.
"""

import warnings

from src.application.workers.factory import WorkerFactory

__all__ = ["WorkerFactory"]

warnings.warn(
    "src.worker_factory is deprecated; use src.application.workers.factory instead",
    DeprecationWarning,
    stacklevel=2,
)
