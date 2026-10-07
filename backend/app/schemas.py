from datetime import datetime
from pydantic import BaseModel, HttpUrl, Field


class URLCreate(BaseModel):
    url: HttpUrl
    custom_alias: str | None = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    expires_at: datetime | None = None


class URLResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    created_at: datetime
    expires_at: datetime | None = None
    click_count: int = 0

    model_config = {"from_attributes": True}


class URLStats(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    click_count: int
    recent_clicks: list["ClickInfo"] = []

    model_config = {"from_attributes": True}


class ClickInfo(BaseModel):
    clicked_at: datetime
    referrer: str | None = None
    user_agent: str | None = None

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    detail: str
