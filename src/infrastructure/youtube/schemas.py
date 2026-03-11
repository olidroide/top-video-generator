"""
Modelos Pydantic para respuestas de la API de YouTube.
Extraídos de client.py (YTPageInfo..YTRoot).
"""

from datetime import datetime

from pydantic import BaseModel


class YTPageInfo(BaseModel):
    totalResults: int
    resultsPerPage: int


class YTBase(BaseModel):
    kind: str
    etag: str
    nextPageToken: str | None = None
    pageInfo: YTPageInfo | None = None


class YTVideoContentDetails(BaseModel):
    duration: str | None = None
    dimension: str | None = None  # 2d
    definition: str | None = None  # hd
    caption: str | None = None
    licensedContent: bool | None = None
    contentRating: dict | None = None
    projection: str | None = None  # rectangular
    videoId: str | None = None
    videoPublishedAt: datetime | None = None


class YTThumbnail(BaseModel):
    url: str
    width: int
    height: int


class YTVideoSnippetThumbnail(BaseModel):
    default: YTThumbnail | None = None
    medium: YTThumbnail | None = None
    high: YTThumbnail | None = None
    standard: YTThumbnail | None = None
    maxres: YTThumbnail | None = None


class YTVideoSnippetLocalized(BaseModel):
    title: str | None = None
    description: str | None = None


class YTVideoSnippetResource(BaseModel):
    videoId: str


class YTVideoSnippet(BaseModel):
    publishedAt: datetime | None = None
    channelId: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnails: YTVideoSnippetThumbnail | None = None
    channelTitle: str | None = None
    tags: list[str] | None = None
    categoryId: str | None = None
    liveBroadcastContent: str | None = None
    localized: YTVideoSnippetLocalized | None = None
    defaultAudioLanguage: str | None = None
    position: int | None = None
    playlistId: str | None = None
    videoOwnerChannelTitle: str | None = None
    videoOwnerChannelId: str | None = None
    resourceId: YTVideoSnippetResource | None = None


class YTVideContentStatistics(BaseModel):
    viewCount: int | None = None
    likeCount: int | None = None
    favoriteCount: int | None = None
    commentCount: int | None = None


class YTVideoStatus(BaseModel):
    embeddable: bool | None = None
    license: str | None = None  # "youtube
    privacyStatus: str | None = None  # "unlisted", "public", "private"
    publicStatsViewable: bool | None = None
    # publishAt
    selfDeclaredMadeForKids: bool | None = None
    madeForKids: bool | None = None
    rejectionReason: str | None = None
    uploadStatus: str | None = None


class YTVideoAgeGating(BaseModel):
    alcoholContent: bool | None = None
    restricted: bool | None = None
    videoGameRating: str | None = None


class YTVideoMonetizationDetailsAccess(BaseModel):
    allowed: bool | None = None


class YTVideoMonetizationDetails(BaseModel):
    access: YTVideoMonetizationDetailsAccess | None = None


class YTVideoTopicDetails(BaseModel):
    relevantTopicIds: list[str] | None = None
    topicCategories: list[str] | None = None
    topicIds: list[str] | None = None


class YTVideo(YTBase):
    id: str
    contentDetails: YTVideoContentDetails | None = None
    snippet: YTVideoSnippet | None = None
    statistics: YTVideContentStatistics | None = None
    status: YTVideoStatus | None = None
    ageGating: YTVideoAgeGating | None = None
    monetizationDetails: YTVideoMonetizationDetails | None = None
    topicDetails: YTVideoTopicDetails | None = None


class YTVideoUploadRequest(YTVideo):
    id: str | None = None


class YTRoot(YTBase):
    items: list[YTVideo]
