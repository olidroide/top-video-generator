"""View models for SSR templates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from src.application.get_setup_page_use_case import GetSetupPageResult
    from src.domain.models import SpotifyAuth, TikTokAuth, Video, YtAuth


@dataclass(frozen=True)
class VideoCardViewModel:
    """Presentation model for a video row."""

    score: int | None
    score_previous: int | None
    score_status: str | None
    yt_video_title_cleaned: str
    channel_name: str
    yt_video_url: str
    yt_video_thumbnail_url: str

    @classmethod
    def from_domain(cls, video: Video) -> VideoCardViewModel:
        return cls(
            score=video.score,
            score_previous=video.score_previous,
            score_status=video.score_status.value if video.score_status else None,
            yt_video_title_cleaned=video.yt_video_title_cleaned,
            channel_name=video.channel.name if video.channel and video.channel.name else "",
            yt_video_url=video.yt_video_url,
            yt_video_thumbnail_url=video.yt_video_thumbnail_url,
        )


@dataclass(frozen=True)
class IndexPageViewModel:
    """Presentation model for the top-videos index page."""

    title_page: str
    video_list: tuple[VideoCardViewModel, ...]
    timeseries_daily_date: date
    timeseries_previous_href: str
    timeseries_next_href: str | None
    timeseries_daily_href: str
    timeseries_weekly_href: str
    is_weekly: bool
    yt_video_published: bool
    credentials_owner: bool

    @property
    def timeseries_mode_label(self) -> str:
        return "Weekly" if self.is_weekly else "Daily"


def build_index_page_view_model(
    *,
    title_flag: str,
    videos: Sequence[Video],
    current_date: date,
    today: date,
    is_weekly: bool,
    yt_video_published: bool,
    credentials_owner: bool,
) -> IndexPageViewModel:
    """Build the page model for the top-videos index SSR template."""
    return IndexPageViewModel(
        title_page=f"{title_flag} 🔝 VIDEO GENERATOR",
        video_list=tuple(VideoCardViewModel.from_domain(video) for video in videos),
        timeseries_daily_date=current_date,
        timeseries_previous_href=f"?daily={(current_date - timedelta(days=1)):%Y-%m-%d}",
        timeseries_next_href=f"?daily={(current_date + timedelta(days=1)):%Y-%m-%d}" if current_date < today else None,
        timeseries_daily_href=f"?daily={current_date:%Y-%m-%d}",
        timeseries_weekly_href=f"?weekly={current_date:%Y-%m-%d}",
        is_weekly=is_weekly,
        yt_video_published=yt_video_published,
        credentials_owner=credentials_owner,
    )


@dataclass(frozen=True)
class SetupPageViewModel:
    """Presentation model for the auth setup page."""

    page_title: str
    yt_authentication_url: str | None
    yt_credentials: YtAuth | None
    tiktok_authentication_url: str | None
    tiktok_credentials: TikTokAuth | None
    spotify_authentication_url: str | None
    spotify_credentials: SpotifyAuth | None


def build_setup_page_view_model(result: GetSetupPageResult) -> SetupPageViewModel:
    """Build the page model for the auth setup SSR template."""
    return SetupPageViewModel(
        page_title="Item Details",
        yt_authentication_url=result.yt_authentication_url,
        yt_credentials=result.yt_credentials,
        tiktok_authentication_url=result.tiktok_authentication_url,
        tiktok_credentials=result.tiktok_credentials,
        spotify_authentication_url=result.spotify_authentication_url,
        spotify_credentials=result.spotify_credentials,
    )
