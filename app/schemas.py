from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator


class LinkCreate(BaseModel):
    target_url: HttpUrl
    custom_alias: str | None = Field(default=None, max_length=32)
    expires_at: datetime | None = None

    @field_validator("custom_alias")
    @classmethod
    def alias_is_url_safe(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return None
        if not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError("alias may only contain letters, numbers, hyphens and underscores")
        return value


class LinkOut(BaseModel):
    short_code: str
    short_url: str
    target_url: str
    created_at: datetime
    expires_at: datetime | None
    click_count: int

    model_config = {"from_attributes": True}


class TimePoint(BaseModel):
    date: str
    clicks: int


class NamedCount(BaseModel):
    name: str
    clicks: int


class LinkStats(BaseModel):
    link: LinkOut
    total_clicks: int
    clicks_by_day: list[TimePoint]
    top_referrers: list[NamedCount]
