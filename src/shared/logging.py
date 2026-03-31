"""Structured logging configuration using structlog."""

import logging.config
import sys
from logging import handlers
from pathlib import Path
from typing import Any, cast

import structlog
from structlog.stdlib import ProcessorFormatter

from src.config.settings import get_app_settings

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")

pre_chain = [
    # Add the log level and a timestamp to the event_dict if the log entry
    # is not from structlog.
    structlog.stdlib.add_log_level,
    # Add extra attributes of LogRecord objects to the event dictionary
    # so that values passed in the extra parameter of log methods pass
    # through to log output.
    structlog.stdlib.ExtraAdder(),
    timestamper,
]


def event_dict_to_message(
    logger: Any, name: str, event_dict: dict[str, Any]
) -> tuple[tuple[dict[str, Any]], dict[str, Any]]:
    """Passes the event_dict to stdlib handler for special formatting."""
    return ((event_dict,), {"extra": {"_logger": logger, "_name": name}})


processors: Any = [
    structlog.stdlib.filter_by_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    timestamper,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    event_dict_to_message,
]

file_processors: Any = [
    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
    structlog.dev.ConsoleRenderer(colors=False),
]


# Configure structlog stack.
structlog.configure(
    processors=cast("Any", processors),
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Use a StreamHandler with a ConsoleRenderer.
handler_stream = logging.StreamHandler(sys.stdout)
handler_stream.setFormatter(ProcessorFormatter(processor=structlog.dev.ConsoleRenderer()))
handler_stream.setLevel(logging.INFO)


log_file_path = Path(get_app_settings().log_file_path)
log_file_path.parent.mkdir(parents=True, exist_ok=True)


handler_file = handlers.TimedRotatingFileHandler(
    filename=log_file_path,
    encoding="utf-8",
    when="midnight",
    backupCount=7,
)
handler_file.setFormatter(
    ProcessorFormatter(
        processors=cast("Any", file_processors),
        foreign_pre_chain=pre_chain,
    )
)
handler_file.setLevel(logging.DEBUG)


# Apply the handlers only to the root logger.
logging.root.setLevel(logging.DEBUG)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.DEBUG)
logging.getLogger("PIL").setLevel(logging.INFO)
logging.root.addHandler(handler_stream)
logging.root.addHandler(handler_file)


def get_logger(*args: Any, **initial_values: Any) -> Any:
    """Return a structlog logger bound with optional initial values."""
    return structlog.get_logger(*args, **initial_values)
