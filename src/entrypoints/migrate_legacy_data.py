"""One-shot migration from legacy TinyDB shared store to split stores."""

from __future__ import annotations

import argparse
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from pydantic import ValidationError
from tinydb import TinyDB

if TYPE_CHECKING:
    from pathlib import Path

from src.config.settings import get_app_settings
from src.domain.models import CanonicalVideo, Platform, Release, SpotifyAuth, TikTokAuth, YtAuth
from src.infrastructure.storage.auth_repository import AuthenticationRepository
from src.infrastructure.storage.release_repository import ReleaseRepository
from src.infrastructure.storage.video_repository import VideoRepository
from src.shared.logging import get_logger, setup_logging
from src.shared.utils import resolve_project_path

logger = get_logger(__name__)

_VIDEO_TABLE_NAMES = frozenset({"video", "videos"})
_RELEASE_TABLE_NAMES = frozenset({"release", "releases"})
_SPOTIFY_TABLE_NAMES = frozenset({"spotify_auth", "spotify"})
_TIKTOK_TABLE_NAMES = frozenset({"tiktok_auth", "tiktok"})
_YT_TABLE_NAMES = frozenset({"yt_auth", "youtube_auth", "youtube", "yt"})
_PLATFORM_ALIASES = {
    "YT": Platform.YOUTUBE.value,
    "YOUTUBE": Platform.YOUTUBE.value,
    "TT": Platform.TIKTOK.value,
    "TIKTOK": Platform.TIKTOK.value,
    "IG": Platform.INSTAGRAM.value,
    "INSTAGRAM": Platform.INSTAGRAM.value,
    "SP": Platform.SPOTIFY.value,
    "SPOTIFY": Platform.SPOTIFY.value,
}


@dataclass
class MigrationSummary:
    apply_changes: bool
    source_db: Path
    video_parsed: int = 0
    video_valid: int = 0
    auth_parsed: int = 0
    auth_valid: int = 0
    release_parsed: int = 0
    release_valid: int = 0
    written_video: int = 0
    written_spotify_auth: int = 0
    written_tiktok_auth: int = 0
    written_yt_auth: int = 0
    written_release: int = 0
    backup_path: Path | None = None
    destination_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)


def _normalize_platform(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return _PLATFORM_ALIASES.get(normalized.upper(), normalized.upper())


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def _to_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return 0
    return int(float(text))


def _classify_source_records(
    records_by_table: dict[str, list[dict[str, object]]],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    video_records: list[dict[str, object]] = []
    spotify_records: list[dict[str, object]] = []
    tiktok_records: list[dict[str, object]] = []
    yt_records: list[dict[str, object]] = []
    release_records: list[dict[str, object]] = []
    leftovers: list[dict[str, object]] = []

    for table_name, records in records_by_table.items():
        lowered = table_name.lower()
        for record in records:
            if lowered in _VIDEO_TABLE_NAMES:
                video_records.append(record)
                continue
            if lowered in _SPOTIFY_TABLE_NAMES:
                spotify_records.append(record)
                continue
            if lowered in _TIKTOK_TABLE_NAMES:
                tiktok_records.append(record)
                continue
            if lowered in _YT_TABLE_NAMES:
                yt_records.append(record)
                continue
            if lowered in _RELEASE_TABLE_NAMES:
                release_records.append(record)
                continue

            if "video_id" in record:
                video_records.append(record)
                continue
            if "platform" in record and ("release_id" in record or "published_at" in record):
                release_records.append(record)
                continue
            if "token_uri" in record or "client_secret" in record:
                yt_records.append(record)
                continue
            if "token" in record and "refresh_token" in record and "client_id" in record:
                leftovers.append(record)
                continue
            leftovers.append(record)

    return video_records, spotify_records, tiktok_records, yt_records, release_records, leftovers


def _to_canonical_video(record: dict[str, object]) -> CanonicalVideo:
    channel_name = ""
    channel_value = record.get("channel")
    if isinstance(channel_value, Mapping):
        channel_data = cast("Mapping[str, object]", channel_value)
        channel_name = str(channel_data.get("name") or "").strip()

    if not channel_name:
        channel_name = str(record.get("channel_name") or "").strip()

    duration_seconds = _to_float(record.get("duration_seconds"))
    if duration_seconds is None:
        duration_seconds = _to_float(record.get("duration"))

    return CanonicalVideo(
        video_id=str(record.get("video_id") or "").strip(),
        title=str(record.get("title") or ""),
        channel_name=channel_name,
        views=_to_int(record.get("views")),
        likes=_to_int(record.get("likes")),
        description=str(record.get("description") or ""),
        duration_seconds=duration_seconds if duration_seconds is not None else 0.0,
    )


def _to_release(record: dict[str, object]) -> Release:
    return Release(
        platform=_normalize_platform(record.get("platform")),
        client_id=str(record.get("client_id") or "").strip() or None,
        release_kind=str(record.get("release_kind") or "").strip() or None,
        release_id=str(record.get("release_id") or "").strip() or None,
        published_at=_to_float(record.get("published_at")),
    )


def _backup_source_file(source_db: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = source_db.with_name(f"{source_db.name}.{timestamp}.bak")
    shutil.copy2(source_db, backup_path)
    return backup_path


def _read_table_records(source_db: Path) -> dict[str, list[dict[str, object]]]:
    source_tinydb = TinyDB(str(source_db))
    try:
        table_names = source_tinydb.tables()
        return {
            table_name: [dict(record) for record in source_tinydb.table(table_name).all()]
            for table_name in sorted(table_names)
        }
    finally:
        source_tinydb.close()


def _collect_destination_counts(video_db: Path, auth_db: Path, release_db: Path) -> dict[str, int]:
    counts: dict[str, int] = {}

    video_tinydb = TinyDB(str(video_db))
    try:
        counts["video"] = len(video_tinydb.table("video"))
    finally:
        video_tinydb.close()

    auth_tinydb = TinyDB(str(auth_db))
    try:
        counts["spotify_auth"] = len(auth_tinydb.table("spotify_auth"))
        counts["tiktok_auth"] = len(auth_tinydb.table("tiktok_auth"))
        counts["yt_auth"] = len(auth_tinydb.table("yt_auth"))
    finally:
        auth_tinydb.close()

    release_tinydb = TinyDB(str(release_db))
    try:
        counts["release"] = len(release_tinydb.table("release"))
    finally:
        release_tinydb.close()

    return counts


def _parse_video_records(records: list[dict[str, object]], summary: MigrationSummary) -> list[CanonicalVideo]:
    videos: list[CanonicalVideo] = []
    for record in records:
        try:
            video = _to_canonical_video(record)
            if not video.video_id:
                summary.warnings.append("Skipped video without video_id")
                continue
            videos.append(video)
        except (ValidationError, TypeError, ValueError) as exc:
            summary.errors.append(f"Invalid video record: {exc}")
    return videos


def _parse_spotify_auth_records(records: list[dict[str, object]], summary: MigrationSummary) -> list[SpotifyAuth]:
    parsed_records: list[SpotifyAuth] = []
    for record in records:
        try:
            parsed_records.append(SpotifyAuth.model_validate(record))
        except ValidationError as exc:
            summary.errors.append(f"Invalid spotify_auth record: {exc}")
    return parsed_records


def _parse_tiktok_auth_records(records: list[dict[str, object]], summary: MigrationSummary) -> list[TikTokAuth]:
    parsed_records: list[TikTokAuth] = []
    for record in records:
        try:
            parsed_records.append(TikTokAuth.model_validate(record))
        except ValidationError as exc:
            summary.errors.append(f"Invalid tiktok_auth record: {exc}")
    return parsed_records


def _parse_yt_auth_records(records: list[dict[str, object]], summary: MigrationSummary) -> list[YtAuth]:
    parsed_records: list[YtAuth] = []
    for record in records:
        try:
            parsed_records.append(YtAuth.model_validate(record))
        except ValidationError as exc:
            summary.errors.append(f"Invalid yt_auth record: {exc}")
    return parsed_records


def _parse_release_records(records: list[dict[str, object]], summary: MigrationSummary) -> list[Release]:
    releases: list[Release] = []
    for record in records:
        try:
            release = _to_release(record)
            if not release.platform:
                summary.warnings.append("Skipped release without platform")
                continue
            if release.platform not in {platform.value for platform in Platform}:
                summary.warnings.append(f"Unknown platform in release kept as-is: {release.platform}")
            if not release.client_id:
                summary.warnings.append("Skipped release without client_id")
                continue
            releases.append(release)
        except (ValidationError, TypeError, ValueError) as exc:
            summary.errors.append(f"Invalid release record: {exc}")
    return releases


def _apply_parsed_records(
    summary: MigrationSummary,
    *,
    source_db: Path,
    video_db: Path,
    auth_db: Path,
    release_db: Path,
    videos: list[CanonicalVideo],
    spotify_auths: list[SpotifyAuth],
    tiktok_auths: list[TikTokAuth],
    yt_auths: list[YtAuth],
    releases: list[Release],
) -> None:
    video_db.parent.mkdir(parents=True, exist_ok=True)
    auth_db.parent.mkdir(parents=True, exist_ok=True)
    release_db.parent.mkdir(parents=True, exist_ok=True)

    summary.backup_path = _backup_source_file(source_db)

    video_repo = VideoRepository(video_db)
    auth_repo = AuthenticationRepository(auth_db)
    release_repo = ReleaseRepository(str(release_db))
    try:
        for video in videos:
            video_repo.upsert(video)
            summary.written_video += 1

        for spotify_auth in spotify_auths:
            auth_repo.add_or_update_spotify_auth(spotify_auth)
            summary.written_spotify_auth += 1

        for tiktok_auth in tiktok_auths:
            auth_repo.add_or_update_tiktok_auth(tiktok_auth)
            summary.written_tiktok_auth += 1

        for yt_auth in yt_auths:
            auth_repo.add_or_update_yt_auth(yt_auth)
            summary.written_yt_auth += 1

        for release in releases:
            release_repo.add_or_update_release(release)
            summary.written_release += 1
    finally:
        video_repo.close()
        auth_repo.close()
        release_repo.close()

    summary.destination_counts = _collect_destination_counts(video_db, auth_db, release_db)


def migrate_legacy_data(
    source_db: Path,
    video_db: Path,
    auth_db: Path,
    release_db: Path,
    *,
    apply_changes: bool,
) -> MigrationSummary:
    summary = MigrationSummary(apply_changes=apply_changes, source_db=source_db)

    if not source_db.exists():
        summary.errors.append(f"Source db not found: {source_db}")
        return summary

    records_by_table = _read_table_records(source_db)
    if not records_by_table:
        summary.warnings.append("Source db has no tables. Nothing to migrate.")
        return summary

    (
        video_records,
        spotify_records,
        tiktok_records,
        yt_records,
        release_records,
        leftovers,
    ) = _classify_source_records(records_by_table)

    summary.video_parsed = len(video_records)
    summary.auth_parsed = len(spotify_records) + len(tiktok_records) + len(yt_records)
    summary.release_parsed = len(release_records)

    if leftovers:
        summary.warnings.append(f"Unclassified records skipped: {len(leftovers)}")

    videos = _parse_video_records(video_records, summary)
    spotify_auths = _parse_spotify_auth_records(spotify_records, summary)
    tiktok_auths = _parse_tiktok_auth_records(tiktok_records, summary)
    yt_auths = _parse_yt_auth_records(yt_records, summary)
    releases = _parse_release_records(release_records, summary)

    summary.video_valid = len(videos)
    summary.auth_valid = len(spotify_auths) + len(tiktok_auths) + len(yt_auths)
    summary.release_valid = len(releases)

    if not apply_changes:
        return summary

    _apply_parsed_records(
        summary,
        source_db=source_db,
        video_db=video_db,
        auth_db=auth_db,
        release_db=release_db,
        videos=videos,
        spotify_auths=spotify_auths,
        tiktok_auths=tiktok_auths,
        yt_auths=yt_auths,
        releases=releases,
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="One-shot migration from db_data.json to split db files")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the command runs in dry-run mode.",
    )
    parser.add_argument("--source", type=str, default=None, help="Source legacy db path")
    parser.add_argument("--video-db", type=str, default=None, help="Destination video db path")
    parser.add_argument("--auth-db", type=str, default=None, help="Destination auth db path")
    parser.add_argument("--release-db", type=str, default=None, help="Destination release db path")
    return parser


def main() -> None:
    settings = get_app_settings()
    setup_logging(settings.log_file_path)

    parser = _build_parser()
    args = parser.parse_args()

    source_db = resolve_project_path(args.source or settings.db_data_file)
    video_db = resolve_project_path(args.video_db or settings.db_video_file)
    auth_db = resolve_project_path(args.auth_db or settings.db_auth_file)
    release_db = resolve_project_path(args.release_db or settings.db_release_file)

    summary = migrate_legacy_data(
        source_db=source_db,
        video_db=video_db,
        auth_db=auth_db,
        release_db=release_db,
        apply_changes=args.apply,
    )

    logger.info(
        "legacy_db_migration.summary",
        apply_changes=summary.apply_changes,
        source_db=str(summary.source_db),
        backup_path=str(summary.backup_path) if summary.backup_path else None,
        video_parsed=summary.video_parsed,
        video_valid=summary.video_valid,
        auth_parsed=summary.auth_parsed,
        auth_valid=summary.auth_valid,
        release_parsed=summary.release_parsed,
        release_valid=summary.release_valid,
        written_video=summary.written_video,
        written_spotify_auth=summary.written_spotify_auth,
        written_tiktok_auth=summary.written_tiktok_auth,
        written_yt_auth=summary.written_yt_auth,
        written_release=summary.written_release,
        destination_counts=summary.destination_counts,
        warning_count=len(summary.warnings),
        error_count=len(summary.errors),
    )

    for warning in summary.warnings[:20]:
        logger.warning("legacy_db_migration.warning", warning=warning)

    for error in summary.errors[:20]:
        logger.error("legacy_db_migration.error", error=error)

    if summary.has_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
