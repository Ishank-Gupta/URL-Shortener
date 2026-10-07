import secrets
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.models import URL

settings = get_settings()


def generate_short_code(length: int | None = None) -> str:
    """Generate a cryptographically random URL-safe short code."""
    length = length or settings.short_code_length
    return secrets.token_urlsafe(length)[:length]


async def get_unique_short_code(db: AsyncSession, length: int | None = None) -> str:
    """Generate a short code that doesn't already exist in the database."""
    for _ in range(10):  # max retries
        code = generate_short_code(length)
        result = await db.execute(select(URL).where(URL.short_code == code))
        if result.scalar_one_or_none() is None:
            return code
    raise RuntimeError("Failed to generate unique short code after 10 attempts")
