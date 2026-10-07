from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import URL, Click
from app.schemas import URLCreate, URLResponse, URLStats, ClickInfo
from app.cache import set_cached_url, delete_cached_url
from app.utils import get_unique_short_code
from app.validators import check_duplicate_url, validate_url_domain
from app.config import get_settings

router = APIRouter(prefix="/api")
settings = get_settings()


@router.post("/shorten", response_model=URLResponse, status_code=201)
async def shorten_url(payload: URLCreate, db: AsyncSession = Depends(get_db)):
    """Create a shortened URL."""
    original_url = str(payload.url)

    # ── Validation ──
    validate_url_domain(original_url)

    # Duplicate detection: if this URL was already shortened, return the existing one
    existing_url = await check_duplicate_url(original_url, db)
    if existing_url:
        return URLResponse(
            short_code=existing_url.short_code,
            short_url=f"{settings.base_url}/{existing_url.short_code}",
            original_url=existing_url.original_url,
            created_at=existing_url.created_at,
            expires_at=existing_url.expires_at,
            click_count=existing_url.click_count,
        )

    # Check for custom alias
    if payload.custom_alias:
        existing = await db.execute(
            select(URL).where(
                (URL.short_code == payload.custom_alias) | (URL.custom_alias == payload.custom_alias)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Custom alias already taken")
        short_code = payload.custom_alias
    else:
        short_code = await get_unique_short_code(db)

    url_entry = URL(
        short_code=short_code,
        original_url=original_url,
        custom_alias=payload.custom_alias,
        expires_at=payload.expires_at,
    )
    db.add(url_entry)
    await db.flush()
    await db.refresh(url_entry)

    # Cache the mapping
    await set_cached_url(short_code, original_url)

    return URLResponse(
        short_code=url_entry.short_code,
        short_url=f"{settings.base_url}/{url_entry.short_code}",
        original_url=url_entry.original_url,
        created_at=url_entry.created_at,
        expires_at=url_entry.expires_at,
        click_count=url_entry.click_count,
    )


@router.get("/urls", response_model=list[URLResponse])
async def list_urls(
    skip: int = 0, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    """List all shortened URLs."""
    result = await db.execute(
        select(URL).order_by(URL.created_at.desc()).offset(skip).limit(limit)
    )
    urls = result.scalars().all()
    return [
        URLResponse(
            short_code=u.short_code,
            short_url=f"{settings.base_url}/{u.short_code}",
            original_url=u.original_url,
            created_at=u.created_at,
            expires_at=u.expires_at,
            click_count=u.click_count,
        )
        for u in urls
    ]


@router.get("/urls/{short_code}/stats", response_model=URLStats)
async def get_url_stats(short_code: str, db: AsyncSession = Depends(get_db)):
    """Get click statistics for a shortened URL."""
    result = await db.execute(select(URL).where(URL.short_code == short_code))
    url_entry = result.scalar_one_or_none()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    clicks_result = await db.execute(
        select(Click)
        .where(Click.url_id == url_entry.id)
        .order_by(Click.clicked_at.desc())
        .limit(100)
    )
    clicks = clicks_result.scalars().all()

    return URLStats(
        short_code=url_entry.short_code,
        original_url=url_entry.original_url,
        created_at=url_entry.created_at,
        click_count=url_entry.click_count,
        recent_clicks=[
            ClickInfo(
                clicked_at=c.clicked_at,
                referrer=c.referrer,
                user_agent=c.user_agent,
            )
            for c in clicks
        ],
    )


@router.delete("/urls/{short_code}", status_code=204)
async def delete_url(short_code: str, db: AsyncSession = Depends(get_db)):
    """Delete a shortened URL."""
    result = await db.execute(select(URL).where(URL.short_code == short_code))
    url_entry = result.scalar_one_or_none()
    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    await delete_cached_url(short_code)
    await db.delete(url_entry)
