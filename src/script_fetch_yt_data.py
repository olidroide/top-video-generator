# ruff: noqa: E402

"""
DEPRECATED: This script has been moved to src.entrypoints.fetch_data.

This shim is for backward compatibility with existing automation.
Scheduled for removal once all references are updated.
"""

import warnings

warnings.warn(
    "src.script_fetch_yt_data is deprecated; use src.entrypoints.fetch_data instead",
    DeprecationWarning,
    stacklevel=2,
)

from src.entrypoints.fetch_data import main, main_async  # noqa: F401

if __name__ == "__main__":
    main()
