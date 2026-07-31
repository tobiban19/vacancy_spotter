"""
Data models and Pydantic schemas for Vacancy Spotter SaaS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic Request / Response Schemas for Telegram Mini App REST API
# ---------------------------------------------------------------------------

class JobCardStatusEnum(str, Enum):
    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    REJECTED = "rejected"
    HIDDEN = "hidden"


class JobCardCreateDTO(BaseModel):
    user_id: int
    channel_title: str = ""
    channel_username: str = ""
    post_text: str
    post_url: str = ""
    post_date: datetime | None = None
    status: JobCardStatusEnum = JobCardStatusEnum.NEW
    match_score: float = 0.0
    matched_keywords: list[str] = Field(default_factory=list)
    draft_reply: str = ""


class JobCardDTO(JobCardCreateDTO):
    id: int
    created_at: datetime


class InitDataAuthRequest(BaseModel):
    init_data: str = Field(..., description="Raw window.Telegram.WebApp.initData string")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    first_name: str
    is_new_user: bool = False


class UserProfileDTO(BaseModel):
    user_id: int
    username: str | None = None
    first_name: str
    profession_id: str = "video_editor"
    experience_years: int = 1
    location: str = "Удалённо"
    stop_words: list[str] = Field(default_factory=list)
    subscription_status: Literal["demo", "active", "expired"] = "demo"
    demo_until: datetime
    subscription_until: datetime | None = None
    bio_summary: str = ""
    software_stack: list[str] = Field(default_factory=list)


class UserProfileUpdateDTO(BaseModel):
    profession_id: str | None = None
    experience_years: int | None = None
    location: str | None = None
    stop_words: list[str] | None = None
    bio_summary: str | None = None
    software_stack: list[str] | None = None


class PortfolioItemCreateDTO(BaseModel):
    title: str = Field(..., max_length=256)
    url: str = Field(..., max_length=2048)
    category: str = Field(default="general", max_length=64)
    orientation: Literal["horizontal", "vertical"] = "horizontal"
    description: str
    tags: list[str] = Field(default_factory=list)


class PortfolioItemDTO(PortfolioItemCreateDTO):
    id: int
    user_id: int
    created_at: datetime


class ProfessionDTO(BaseModel):
    id: str
    title_ru: str
    icon_emoji: str


class ChannelDTO(BaseModel):
    id: int
    profession_id: str
    username: str
    title: str
    is_recommended: bool = True
    is_enabled: bool = True


class ChannelCustomAddDTO(BaseModel):
    username_or_link: str


class SubscriptionStatusDTO(BaseModel):
    status: Literal["demo", "active", "expired"]
    demo_until: datetime
    subscription_until: datetime | None = None
    days_left: int
    is_valid: bool


# ---------------------------------------------------------------------------
# Admin DTOs
# ---------------------------------------------------------------------------

class AdminUserDTO(BaseModel):
    user_id: int
    username: str | None = None
    first_name: str
    profession_id: str
    subscription_status: str
    demo_until: datetime
    subscription_until: datetime | None = None
    is_banned: bool = False
    ban_reason: str | None = None
    channels_count: int = 0
    created_at: datetime


class AdminStatsDTO(BaseModel):
    total_users: int
    active_paid_users: int
    demo_users: int
    expired_users: int
    banned_users: int


class AdminUserDetailDTO(BaseModel):
    profile: UserProfileDTO
    is_banned: bool
    ban_reason: str | None
    bio_summary: str
    software_stack: list[str]
    stop_words: list[str]
    connected_channels: list[dict[str, Any]]
    created_at: datetime


class AdminSubscriptionUpdateDTO(BaseModel):
    action: Literal["add_days", "set_status", "revoke"]
    days: int | None = None
    status: Literal["demo", "active", "expired"] | None = None


class AdminBanUpdateDTO(BaseModel):
    is_banned: bool
    ban_reason: str | None = None

