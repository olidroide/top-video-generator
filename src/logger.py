import logging.config
import sys
from logging import handlers
from typing import Any

import structlog
from structlog.stdlib import ProcessorFormatter

from src.settings import get_app_settings

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")
# timestamper = structlog.processors.TimeStamper(fmt="iso")

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


def event_dict_to_message(logger, name, event_dict):
    """Passes the event_dict to stdlib handler for special formatting."""
    return ((event_dict,), {"extra": {"_logger": logger, "_name": name}})


# Configure structlog stack.
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        # Do not include last processor that converts to a string for stdlib
        # since we leave that to the handler's formatter.
        event_dict_to_message,
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Use a StreamHandler with a ConsoleRenderer.
handler_stream = logging.StreamHandler(sys.stdout)
handler_stream.setFormatter(ProcessorFormatter(processor=structlog.dev.ConsoleRenderer()))
handler_stream.setLevel(logging.INFO)


handler_file = handlers.TimedRotatingFileHandler(
    filename=get_app_settings().log_file_path,
    encoding="utf-8",
    when="midnight",
    backupCount=7,
)
handler_file.setFormatter(
    ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        foreign_pre_chain=pre_chain,
    )
)
handler_file.setLevel(logging.DEBUG)


# Library logger to info level.
# logger = structlog.get_logger("lib")
# logger.setLevel(logging.DEBUG)

# Apply the handlers only to the root logger.
logging.root.setLevel(logging.DEBUG)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.DEBUG)
logging.getLogger("PIL").setLevel(logging.INFO)
logging.root.addHandler(handler_stream)
logging.root.addHandler(handler_file)


def get_logger(*args: Any, **initial_values: Any) -> Any:
    return structlog.get_logger(*args, **initial_values)
