"""Basic tests for AtomicFileStorage functionality."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.shared.atomic_storage import AtomicFileStorage


class TestAtomicFileStorageBasic:
    """Verify AtomicFileStorage read/write operations."""

    def test_read_write_json_basic(self) -> None:
        """Test basic read and write operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AtomicFileStorage(f"{tmpdir}/test.json")

            # Write initial data
            data = {"key1": "value1", "key2": {"nested": "value2"}}
            storage.write_json(data)

            # Read back
            read_data = storage.read_json()
            assert read_data == data

    def test_read_missing_file_returns_empty_dict(self) -> None:
        """Test reading non-existent file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AtomicFileStorage(f"{tmpdir}/missing.json")
            result = storage.read_json()
            assert result == {}

    def test_locked_read_write_context_manager(self) -> None:
        """Test locked_read_write context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AtomicFileStorage(f"{tmpdir}/test.json")

            # Initial write
            storage.write_json({"counter": 1})

            # Modify via context manager
            with storage.locked_read_write() as data:
                data["counter"] = 2
                data["new_key"] = "new_value"

            # Verify changes persisted
            read_data = storage.read_json()
            assert read_data["counter"] == 2
            assert read_data["new_key"] == "new_value"

    def test_locked_read_write_creates_file_if_missing(self) -> None:
        """Test context manager creates file if absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AtomicFileStorage(f"{tmpdir}/new.json")

            with storage.locked_read_write() as data:
                data["initial"] = "value"

            # File should exist
            assert Path(f"{tmpdir}/new.json").exists()

            # Content should be readable
            read_data = storage.read_json()
            assert read_data["initial"] == "value"

    def test_write_json_overwrites_previous(self) -> None:
        """Test write_json replaces entire file content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = AtomicFileStorage(f"{tmpdir}/test.json")

            # Write initial
            storage.write_json({"old": "data"})

            # Write new (should replace)
            storage.write_json({"new": "data"})

            # Only new data present
            result = storage.read_json()
            assert result == {"new": "data"}
            assert "old" not in result

    def test_empty_file_returns_empty_dict(self) -> None:
        """Test empty JSON file returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "empty.json"
            file_path.touch()  # Create empty file

            storage = AtomicFileStorage(str(file_path))
            result = storage.read_json()
            assert result == {}
