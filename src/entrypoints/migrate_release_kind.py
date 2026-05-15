"""Idempotent migration: infer release_kind from published_at timestamp.

Legacy releases were stored with release_kind=None. This script infers the release_kind
based on the day of the week the video was published:
- Friday → WEEKLY_HORIZONTAL
- Other days → DAILY_VERTICAL

This migration is idempotent: running it multiple times produces the same result.
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from src.domain.models import ReleaseKind
from src.shared.logging import get_logger

logger = get_logger(__name__)

FRIDAY_WEEKDAY = 4


def infer_release_kind(published_at: float) -> str:
    """Infer release kind from published_at timestamp.

    Args:
        published_at: Unix timestamp (float).

    Returns:
        ReleaseKind.WEEKLY_HORIZONTAL if published on Friday, else ReleaseKind.DAILY_VERTICAL.
    """
    published_dt = datetime.fromtimestamp(published_at, tz=UTC)
    # weekday() returns 0=Monday, 1=Tuesday, ..., 4=Friday, 5=Saturday, 6=Sunday
    is_friday = published_dt.weekday() == FRIDAY_WEEKDAY
    return ReleaseKind.WEEKLY_HORIZONTAL if is_friday else ReleaseKind.DAILY_VERTICAL


def migrate_release_kind(db_path: str, backup_suffix: str = ".pre_migration") -> dict[str, int]:
    """Migrate release records from null release_kind to inferred values.

    Args:
        db_path: Path to db_release.json file.
        backup_suffix: Suffix for backup file (default: .pre_migration).

    Returns:
        Dictionary with migration statistics:
        - total_records: Total records processed.
        - migrated: Records that had release_kind=None and were updated.
        - skipped: Records that already had release_kind set.
        - errors: Number of errors encountered.
    """
    db_file = Path(db_path)

    if not db_file.exists():
        logger.error("Database file not found: %s", db_path)
        return {"total_records": 0, "migrated": 0, "skipped": 0, "errors": 1}

    # Load current state
    try:
        with db_file.open(encoding="utf-8") as f:
            db_contents = json.load(f)
    except json.JSONDecodeError:
        logger.exception("Failed to parse database JSON")
        return {"total_records": 0, "migrated": 0, "skipped": 0, "errors": 1}

    release_table = db_contents.get("release", {})
    stats = {"total_records": len(release_table), "migrated": 0, "skipped": 0, "errors": 0}

    # Migrate each record
    for doc_id, record in release_table.items():
        try:
            if record.get("release_kind") is None:
                published_at = record.get("published_at")
                if published_at is None:
                    logger.warning("Record %s has no published_at timestamp, skipping", doc_id)
                    stats["errors"] += 1
                    continue

                # Infer and set release_kind
                inferred_kind = infer_release_kind(published_at)
                record["release_kind"] = inferred_kind
                stats["migrated"] += 1

                published_dt = datetime.fromtimestamp(published_at, tz=UTC)
                logger.info(
                    "Migrated record %s: published_at=%s, release_kind=%s",
                    doc_id,
                    published_dt.isoformat(),
                    inferred_kind,
                )
            else:
                stats["skipped"] += 1
        except Exception:
            logger.exception("Error processing record %s", doc_id)
            stats["errors"] += 1

    # If no migrations needed, return early
    if stats["migrated"] == 0:
        logger.info("No migrations needed; all records already have release_kind set")
        return stats

    # Create backup before writing
    backup_file = db_file.parent / (db_file.name + backup_suffix)
    try:
        shutil.copy2(db_file, backup_file)
        logger.info("Created backup: %s", backup_file)
    except Exception:
        logger.exception("Failed to create backup")
        stats["errors"] += 1
        return stats

    # Write migrated data back
    try:
        with db_file.open("w", encoding="utf-8") as f:
            json.dump(db_contents, f, separators=(",", ":"))
        logger.info("Updated %s records in %s", stats["migrated"], db_path)
    except Exception:
        logger.exception("Failed to write database")
        stats["errors"] += 1

    return stats


def main() -> None:
    """CLI entry point for migration."""
    parser = argparse.ArgumentParser(
        description="Migrate release_kind from null to inferred values based on published_at day of week"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="db/db_release.json",
        help="Path to db_release.json (default: db/db_release.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing changes",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN MODE: No changes will be written")
        # For dry run, just load and report what would be changed
        db_file = Path(args.db_path)
        if not db_file.exists():
            logger.error("Database file not found: %s", args.db_path)
            return

        with db_file.open(encoding="utf-8") as f:
            db_contents = json.load(f)

        release_table = db_contents.get("release", {})
        dry_run_count = 0
        for doc_id, record in release_table.items():
            if record.get("release_kind") is None:
                published_at = record.get("published_at")
                if published_at is not None:
                    inferred_kind = infer_release_kind(published_at)
                    published_dt = datetime.fromtimestamp(published_at, tz=UTC)
                    logger.info(
                        "[DRY RUN] Would migrate record %s: published_at=%s, release_kind=%s",
                        doc_id,
                        published_dt.isoformat(),
                        inferred_kind,
                    )
                    dry_run_count += 1
        logger.info("[DRY RUN] Would migrate %s records", dry_run_count)
        return

    # Perform actual migration
    stats = migrate_release_kind(args.db_path)
    logger.info(
        "Migration complete: total=%s, migrated=%s, skipped=%s, errors=%s",
        stats["total_records"],
        stats["migrated"],
        stats["skipped"],
        stats["errors"],
    )


if __name__ == "__main__":
    main()
