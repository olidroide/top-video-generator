"""Tests for release_kind migration script."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.domain.models import ReleaseKind
from src.entrypoints.migrate_release_kind import infer_release_kind, migrate_release_kind


class TestInferReleaseKind:
    """Tests for release_kind inference based on day of week."""

    def test_friday_infers_weekly_horizontal(self) -> None:
        """Verify Friday-published videos get WEEKLY_HORIZONTAL."""
        # Friday, May 16, 2025 at 12:00 UTC = 1747396800
        friday_timestamp = 1747396800.0
        result = infer_release_kind(friday_timestamp)
        assert result == ReleaseKind.WEEKLY_HORIZONTAL

    def test_monday_infers_daily_vertical(self) -> None:
        """Verify Monday-published videos get DAILY_VERTICAL."""
        # Monday, May 19, 2025 at 12:00 UTC = 1747656000
        monday_timestamp = 1747656000.0
        result = infer_release_kind(monday_timestamp)
        assert result == ReleaseKind.DAILY_VERTICAL

    def test_wednesday_infers_daily_vertical(self) -> None:
        """Verify Wednesday-published videos get DAILY_VERTICAL."""
        # Wednesday, May 14, 2025 at 12:00 UTC = 1747224000
        wednesday_timestamp = 1747224000.0
        result = infer_release_kind(wednesday_timestamp)
        assert result == ReleaseKind.DAILY_VERTICAL

    def test_saturday_infers_daily_vertical(self) -> None:
        """Verify Saturday-published videos get DAILY_VERTICAL."""
        # Saturday, May 17, 2025 at 12:00 UTC = 1747483200
        saturday_timestamp = 1747483200.0
        result = infer_release_kind(saturday_timestamp)
        assert result == ReleaseKind.DAILY_VERTICAL


class TestMigrateReleaseKind:
    """Tests for release_kind migration script."""

    def test_migrate_null_release_kind_records(self) -> None:
        """Verify null release_kind records are migrated to inferred values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_release.json"

            # Create test database with mixed null and non-null release_kind
            db_contents = {
                "release": {
                    "1": {
                        "platform": "YOUTUBE",
                        "client_id": "test_yt_client",
                        "release_kind": None,
                        "release_id": "vid_001",
                        "published_at": 1747396800.0,  # Friday
                    },
                    "2": {
                        "platform": "TIKTOK",
                        "client_id": "test_tt_client",
                        "release_kind": None,
                        "release_id": "vid_002",
                        "published_at": 1747656000.0,  # Monday
                    },
                    "3": {
                        "platform": "INSTAGRAM",
                        "client_id": "test_ig_client",
                        "release_kind": "DAILY_VERTICAL",  # Already set
                        "release_id": "vid_003",
                        "published_at": 1747224000.0,
                    },
                }
            }

            with db_file.open("w") as f:
                json.dump(db_contents, f)

            # Run migration
            stats = migrate_release_kind(str(db_file))

            # Verify stats
            assert stats["total_records"] == 3
            assert stats["migrated"] == 2
            assert stats["skipped"] == 1
            assert stats["errors"] == 0

            # Verify migrated values
            with db_file.open() as f:
                migrated_db = json.load(f)

            release_1 = migrated_db["release"]["1"]
            assert release_1["release_kind"] == ReleaseKind.WEEKLY_HORIZONTAL

            release_2 = migrated_db["release"]["2"]
            assert release_2["release_kind"] == ReleaseKind.DAILY_VERTICAL

            release_3 = migrated_db["release"]["3"]
            assert release_3["release_kind"] == "DAILY_VERTICAL"  # Unchanged

    def test_migration_idempotence(self) -> None:
        """Verify running migration twice produces same result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_release.json"

            db_contents = {
                "release": {
                    "1": {
                        "platform": "YOUTUBE",
                        "client_id": "test_yt",
                        "release_kind": None,
                        "release_id": "vid_001",
                        "published_at": 1747396800.0,
                    }
                }
            }

            with db_file.open("w") as f:
                json.dump(db_contents, f)

            # First migration
            _stats1 = migrate_release_kind(str(db_file))
            with db_file.open() as f:
                after_first = json.load(f)

            # Second migration
            stats2 = migrate_release_kind(str(db_file))
            with db_file.open() as f:
                after_second = json.load(f)

            # Verify idempotence
            assert after_first == after_second
            assert stats2["migrated"] == 0
            assert stats2["skipped"] == 1

    def test_backup_creation(self) -> None:
        """Verify backup file is created before migration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_release.json"

            db_contents = {
                "release": {
                    "1": {
                        "platform": "YOUTUBE",
                        "client_id": "test_yt",
                        "release_kind": None,
                        "release_id": "vid_001",
                        "published_at": 1747396800.0,
                    }
                }
            }

            with db_file.open("w") as f:
                json.dump(db_contents, f)

            migrate_release_kind(str(db_file))

            backup_file = Path(str(db_file) + ".pre_migration")
            assert backup_file.exists(), "Backup file should be created"

            with backup_file.open() as f:
                backup_contents = json.load(f)

            # Verify backup has original null value
            assert backup_contents["release"]["1"]["release_kind"] is None

    def test_missing_published_at_field(self) -> None:
        """Verify records with missing published_at are counted as errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_release.json"

            db_contents = {
                "release": {
                    "1": {
                        "platform": "YOUTUBE",
                        "client_id": "test_yt",
                        "release_kind": None,
                        "release_id": "vid_001",
                        # Missing published_at
                    }
                }
            }

            with db_file.open("w") as f:
                json.dump(db_contents, f)

            stats = migrate_release_kind(str(db_file))

            assert stats["errors"] == 1
            assert stats["migrated"] == 0

    def test_nonexistent_database_file(self) -> None:
        """Verify graceful handling of missing database file."""
        stats = migrate_release_kind("/nonexistent/path/db_release.json")

        assert stats["total_records"] == 0
        assert stats["errors"] == 1

    def test_no_migrations_needed(self) -> None:
        """Verify behavior when all records already have release_kind set."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_file = Path(tmpdir) / "db_release.json"

            db_contents = {
                "release": {
                    "1": {
                        "platform": "YOUTUBE",
                        "client_id": "test_yt",
                        "release_kind": "WEEKLY_HORIZONTAL",
                        "release_id": "vid_001",
                        "published_at": 1747396800.0,
                    },
                    "2": {
                        "platform": "TIKTOK",
                        "client_id": "test_tt",
                        "release_kind": "DAILY_VERTICAL",
                        "release_id": "vid_002",
                        "published_at": 1747656000.0,
                    },
                }
            }

            with db_file.open("w") as f:
                json.dump(db_contents, f)

            stats = migrate_release_kind(str(db_file))

            assert stats["total_records"] == 2
            assert stats["migrated"] == 0
            assert stats["skipped"] == 2
            assert stats["errors"] == 0
