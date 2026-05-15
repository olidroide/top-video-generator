"""Unit tests for explicit logging setup helpers."""

from pathlib import Path

from src.shared import logging as logging_module


def _cleanup_configured_handlers() -> None:
    for handler in tuple(logging_module._configured_handlers):
        logging_module.logging.root.removeHandler(handler)
        handler.close()
    logging_module._configured_handlers.clear()


def test_setup_logging_replaces_owned_handlers_without_duplication(tmp_path: Path) -> None:
    _cleanup_configured_handlers()
    try:
        first_log_file = tmp_path / "first" / "app.log"
        logging_module.setup_logging(first_log_file)
        first_handlers = list(logging_module._configured_handlers)

        assert len(first_handlers) == 2
        assert all(handler in logging_module.logging.root.handlers for handler in first_handlers)
        assert first_log_file.exists()

        second_log_file = tmp_path / "second" / "app.log"
        logging_module.setup_logging(second_log_file)

        assert len(logging_module._configured_handlers) == 2
        assert second_log_file.exists()
        assert all(handler not in logging_module.logging.root.handlers for handler in first_handlers)
        assert all(handler in logging_module.logging.root.handlers for handler in logging_module._configured_handlers)
    finally:
        _cleanup_configured_handlers()
