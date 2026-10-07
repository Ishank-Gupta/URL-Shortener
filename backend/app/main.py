from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import engine, get_db
from app.models import Base, URL, Click
from app.cache import get_cached_url, set_cached_url, check_rate_limit
from app.config import get_settings
from app.routes import router
from app.validators import register_self_host

settings = get_settings()

# Paths that should never be treated as short codes
RESERVED_PATHS = {"docs", "redoc", "openapi.json", "health", "api", "favicon.ico"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register our own domain so users can't create redirect loops
    register_self_host(settings.base_url)
    # Create tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup on shutdown
    await engine.dispose()


app = FastAPI(
    title="URL Shortener",
    description="A fast, simple URL shortening service",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/{short_code}")
async def redirect_to_url(short_code: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Redirect a short code to its original URL."""
    # Skip reserved paths — let FastAPI handle them
    if short_code in RESERVED_PATHS:
        raise HTTPException(status_code=404, detail="Not found")

    # Rate limiting
    client_ip = request.client.host if request.client else "unknown"
    if not await check_rate_limit(client_ip, settings.rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Try cache first
    cached_url = await get_cached_url(short_code)
    if cached_url:
        # Record click with atomic increment — no SELECT needed
        await db.execute(
            update(URL)
            .where(URL.short_code == short_code)
            .values(click_count=URL.click_count + 1)
        )
        # Get url_id for click record
        result = await db.execute(
            select(URL.id).where(URL.short_code == short_code)
        )
        url_id = result.scalar_one_or_none()
        if url_id:
            db.add(Click(
                url_id=url_id,
                referrer=request.headers.get("referer"),
                user_agent=request.headers.get("user-agent"),
                ip_address=client_ip,
            ))
        return RedirectResponse(url=cached_url, status_code=302)

    # Cache miss — query DB
    result = await db.execute(select(URL).where(URL.short_code == short_code))
    url_entry = result.scalar_one_or_none()

    if not url_entry:
        raise HTTPException(status_code=404, detail="Short URL not found")

    # Check expiration
    if url_entry.expires_at and url_entry.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This short URL has expired")

    # Cache the mapping
    await set_cached_url(short_code, url_entry.original_url)

    # Atomic click count increment
    await db.execute(
        update(URL)
        .where(URL.id == url_entry.id)
        .values(click_count=URL.click_count + 1)
    )

    db.add(Click(
        url_id=url_entry.id,
        referrer=request.headers.get("referer"),
        user_agent=request.headers.get("user-agent"),
        ip_address=client_ip,
    ))

    return RedirectResponse(url=url_entry.original_url, status_code=302)
