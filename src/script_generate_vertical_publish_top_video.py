# ruff: noqa: E402

"""
DEPRECATED: This script has been moved to src.entrypoints.publish_vertical.

This shim is for backward compatibility with existing automation.
Scheduled for removal once all references are updated.
"""

import warnings

warnings.warn(
    "src.script_generate_vertical_publish_top_video is deprecated; use src.entrypoints.publish_vertical instead",
    DeprecationWarning,
    stacklevel=2,
)

from src.entrypoints.publish_vertical import main, main_async  # noqa: F401

if __name__ == "__main__":
    main()
