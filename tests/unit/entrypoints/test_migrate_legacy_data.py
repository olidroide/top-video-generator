from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB

from src.entrypoints.migrate_legacy_data import migrate_legacy_data


def _seed_legacy_db(path: Path) -> None:
    db = TinyDB(str(path))
    try:
        db.table("video").insert(
            {
                "video_id": "abc123",
                "title": "Song",
                "channel": {"name": "Channel A"},
                "views": 100,
                "likes": 10,
                "description": "desc",
                "duration": 180,
            }
        )
        db.table("video").insert({"title": "missing id"})

        db.table("spotify_auth").insert(
            {
                "client_id": "spotify-client",
                "token": "token-a",
                "refresh_token": "refresh-a",
                "scopes": ["playlist-modify-public"],
            }
        )
        db.table("yt_auth").insert(
            {
                "client_id": "yt-client",
                "token": "token-y",
                "refresh_token": "refresh-y",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_secret": "secret",
                "scopes": ["youtube.upload"],
            }
        )
        db.table("release").insert(
            {
                "platform": "youtube",
                "client_id": "yt-user",
                "release_kind": "WEEKLY_HORIZONTAL",
                "release_id": "yt-video-id",
                "published_at": 1_700_000_000,
            }
        )
        db.table("release").insert(
            {
                "platform": "YT",
                "client_id": "yt-user-legacy",
                "release_kind": "WEEKLY_HORIZONTAL",
                "release_id": "yt-video-id-legacy",
                "published_at": 1_700_000_001,
            }
        )
    finally:
        db.close()


def test_migrate_legacy_data_dry_run_does_not_write_files(tmp_path: Path) -> None:
    source_db = tmp_path / "db_data.json"
    _seed_legacy_db(source_db)

    video_db = tmp_path / "db_video.json"
    auth_db = tmp_path / "db_auth.json"
    release_db = tmp_path / "db_release.json"

    summary = migrate_legacy_data(
        source_db=source_db,
        video_db=video_db,
        auth_db=auth_db,
        release_db=release_db,
        apply_changes=False,
    )

    assert summary.video_parsed == 2
    assert summary.video_valid == 1
    assert summary.auth_parsed == 2
    assert summary.auth_valid == 2
    assert summary.release_parsed == 2
    assert summary.release_valid == 2
    assert summary.written_video == 0
    assert summary.written_spotify_auth == 0
    assert summary.written_yt_auth == 0
    assert summary.written_release == 0
    assert summary.backup_path is None
    assert not video_db.exists()
    assert not auth_db.exists()
    assert not release_db.exists()


def test_migrate_legacy_data_apply_writes_destinations_and_backup(tmp_path: Path) -> None:
    source_db = tmp_path / "db_data.json"
    _seed_legacy_db(source_db)

    video_db = tmp_path / "db_video.json"
    auth_db = tmp_path / "db_auth.json"
    release_db = tmp_path / "db_release.json"

    summary = migrate_legacy_data(
        source_db=source_db,
        video_db=video_db,
        auth_db=auth_db,
        release_db=release_db,
        apply_changes=True,
    )

    assert summary.backup_path is not None
    assert summary.backup_path.exists()

    video_tinydb = TinyDB(str(video_db))
    try:
        video_rows = video_tinydb.table("video").all()
    finally:
        video_tinydb.close()

    assert len(video_rows) == 1
    assert video_rows[0]["video_id"] == "abc123"
    assert video_rows[0]["channel_name"] == "Channel A"

    auth_tinydb = TinyDB(str(auth_db))
    try:
        spotify_rows = auth_tinydb.table("spotify_auth").all()
        yt_rows = auth_tinydb.table("yt_auth").all()
    finally:
        auth_tinydb.close()

    assert len(spotify_rows) == 1
    assert len(yt_rows) == 1

    release_tinydb = TinyDB(str(release_db))
    try:
        release_rows = release_tinydb.table("release").all()
    finally:
        release_tinydb.close()

    assert len(release_rows) == 2
    assert {row["platform"] for row in release_rows} == {"YOUTUBE"}

    assert summary.destination_counts["video"] == 1
    assert summary.destination_counts["spotify_auth"] == 1
    assert summary.destination_counts["yt_auth"] == 1
    assert summary.destination_counts["release"] == 2
