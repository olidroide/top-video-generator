"""
Pydantic models for YouTube API responses.
Extracted from client.py (YTPageInfo..YTRoot).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class YTSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)


class YTPageInfo(YTSchema):
    total_results: int
    results_per_page: int


class YTBase(YTSchema):
    kind: str
    etag: str
    next_page_token: str | None = None
    page_info: YTPageInfo | None = None


class YTVideoContentDetails(YTSchema):
    duration: str | None = None
    dimension: str | None = None  # 2d
    definition: str | None = None  # hd
    caption: str | None = None
    licensed_content: bool | None = None
    content_rating: dict | None = None
    projection: str | None = None  # rectangular
    video_id: str | None = None
    video_published_at: datetime | None = None


class YTThumbnail(YTSchema):
    url: str
    width: int
    height: int


class YTVideoSnippetThumbnail(YTSchema):
    default: YTThumbnail | None = None
    medium: YTThumbnail | None = None
    high: YTThumbnail | None = None
    standard: YTThumbnail | None = None
    maxres: YTThumbnail | None = None


class YTVideoSnippetLocalized(YTSchema):
    title: str | None = None
    description: str | None = None


class YTVideoSnippetResource(YTSchema):
    video_id: str


class YTVideoSnippet(YTSchema):
    published_at: datetime | None = None
    channel_id: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnails: YTVideoSnippetThumbnail | None = None
    channel_title: str | None = None
    tags: list[str] | None = None
    category_id: str | None = None
    live_broadcast_content: str | None = None
    localized: YTVideoSnippetLocalized | None = None
    default_audio_language: str | None = None
    position: int | None = None
    playlist_id: str | None = None
    video_owner_channel_title: str | None = None
    video_owner_channel_id: str | None = None
    resource_id: YTVideoSnippetResource | None = None


class YTVideContentStatistics(YTSchema):
    view_count: int | None = None
    like_count: int | None = None
    favorite_count: int | None = None
    comment_count: int | None = None


class YTVideoStatus(YTSchema):
    embeddable: bool | None = None
    license: str | None = None  # "youtube
    privacy_status: str | None = None  # "unlisted", "public", "private"
    public_stats_viewable: bool | None = None
    # publishAt
    self_declared_made_for_kids: bool | None = None
    made_for_kids: bool | None = None
    rejection_reason: str | None = None
    upload_status: str | None = None


class YTVideoAgeGating(YTSchema):
    alcohol_content: bool | None = None
    restricted: bool | None = None
    video_game_rating: str | None = None


class YTVideoMonetizationDetailsAccess(YTSchema):
    allowed: bool | None = None


class YTVideoMonetizationDetails(YTSchema):
    access: YTVideoMonetizationDetailsAccess | None = None


class YTVideoTopicDetails(YTSchema):
    relevant_topic_ids: list[str] | None = None
    topic_categories: list[str] | None = None
    topic_ids: list[str] | None = None


class YTVideo(YTBase):
    id: str
    content_details: YTVideoContentDetails | None = None
    snippet: YTVideoSnippet | None = None
    statistics: YTVideContentStatistics | None = None
    status: YTVideoStatus | None = None
    age_gating: YTVideoAgeGating | None = None
    monetization_details: YTVideoMonetizationDetails | None = None
    topic_details: YTVideoTopicDetails | None = None


class YTVideoUploadRequest(YTVideo):
    id: str | None = None


class YTRoot(YTBase):
    items: list[YTVideo]
