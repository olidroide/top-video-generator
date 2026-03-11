# ruff: noqa: E402

"""
DEPRECATED: This module has been moved to src.application.workers.post_processor.

This shim is here to maintain backward compatibility.
Scheduled for removal when all subprocess calls are updated.
"""

import warnings

warnings.warn(
    "src.worker_post_process_video is deprecated; use src.application.workers.post_processor instead",
    DeprecationWarning,
    stacklevel=2,
)

# Forward to the new module for direct execution (if needed)
from src.application.workers.post_processor import main_main  # noqa: F401

if __name__ == "__main__":
    import sys

    script_name = sys.argv
    arguments = sys.argv[1].strip().split(" ")
    port = int(arguments[0])
    screen_orientation = str(arguments[1])
    main_main(port, screen_orientation)
