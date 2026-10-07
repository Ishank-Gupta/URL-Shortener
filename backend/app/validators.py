"""URL validation: blocked domains and duplicate detection."""

from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import URL

# Domains that should never be shortened (self-referencing, abuse magnets)
BLOCKED_DOMAINS: set[str] = {
    # Self-referencing — prevent redirect loops
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    # Common abuse / phishing targets
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "is.gd",
    "rb.gy",
    "shorturl.at",
    "cutt.ly",
}

# Also block any domain that matches our own service
_SELF_HOSTS: set[str] = set()


def register_self_host(base_url: str) -> None:
    """Call once at startup so the validator blocks our own domain."""
    parsed = urlparse(base_url)
    if parsed.hostname:
        _SELF_HOSTS.add(parsed.hostname.lower())


def validate_url_domain(original_url: str) -> None:
    """Raise 400 if the URL targets a blocked domain."""
    parsed = urlparse(original_url)
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        raise HTTPException(status_code=400, detail="Invalid URL: no hostname found")

    if hostname in BLOCKED_DOMAINS or hostname in _SELF_HOSTS:
        raise HTTPException(
            status_code=400,
            detail=f"Shortening URLs from '{hostname}' is not allowed",
        )

    # Block private/reserved IP ranges (simple check for common patterns)
    if hostname.startswith("10.") or hostname.startswith("192.168.") or hostname.startswith("172."):
        raise HTTPException(
            status_code=400,
            detail="Shortening URLs pointing to private IP addresses is not allowed",
        )


async def check_duplicate_url(
    original_url: str,
    db: AsyncSession,
) -> URL | None:
    """Return an existing URL entry if the same URL was already shortened."""
    result = await db.execute(
        select(URL).where(URL.original_url == original_url)
    )
    return result.scalar_one_or_none()
