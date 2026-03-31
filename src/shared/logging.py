"""Structured logging helpers using structlog."""

import logging
import sys
from logging import handlers
from pathlib import Path
from typing import Any

import structlog
from structlog.stdlib import ProcessorFormatter

timestamper = structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S")

pre_chain: list[Any] = [
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


processors: list[Any] = [
    structlog.stdlib.filter_by_level,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    timestamper,
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    event_dict_to_message,
]

file_processors: list[Any] = [
    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
    structlog.dev.ConsoleRenderer(colors=False),
]


_configured_handlers: list[logging.Handler] = []


def _reset_configured_handlers() -> None:
    for handler in tuple(_configured_handlers):
        logging.root.removeHandler(handler)
        handler.close()
    _configured_handlers.clear()


def _build_stream_handler() -> logging.Handler:
    handler_stream = logging.StreamHandler(sys.stdout)
    handler_stream.setFormatter(ProcessorFormatter(processor=structlog.dev.ConsoleRenderer()))
    handler_stream.setLevel(logging.INFO)
    return handler_stream


def _build_file_handler(log_file_path: Path) -> logging.Handler:
    log_file_path.parent.mkdir(parents=True, exist_ok=True)
    handler_file = handlers.TimedRotatingFileHandler(
        filename=log_file_path,
        encoding="utf-8",
        when="midnight",
        backupCount=7,
    )
    handler_file.setFormatter(
        ProcessorFormatter(
            processors=file_processors,
            foreign_pre_chain=pre_chain,
        )
    )
    handler_file.setLevel(logging.DEBUG)
    return handler_file


def setup_logging(log_file_path: Path | str) -> None:
    """Explicitly initialize root logging handlers and structlog."""
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    _reset_configured_handlers()

    stream_handler = _build_stream_handler()
    file_handler = _build_file_handler(Path(log_file_path))

    logging.root.setLevel(logging.DEBUG)
    logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.DEBUG)
    logging.getLogger("PIL").setLevel(logging.INFO)
    logging.root.addHandler(stream_handler)
    logging.root.addHandler(file_handler)
    _configured_handlers.extend([stream_handler, file_handler])


def get_logger(*args: Any, **initial_values: Any) -> Any:
    """Return a structlog logger bound with optional initial values."""
    return structlog.get_logger(*args, **initial_values)
