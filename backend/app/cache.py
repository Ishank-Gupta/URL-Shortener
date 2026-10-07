import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

CACHE_TTL = 3600  # 1 hour

# Lua script for atomic rate limiting: INCR + conditional EXPIRE in one round-trip
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return current
"""


async def get_cached_url(short_code: str) -> str | None:
    """Get original URL from Redis cache."""
    return await redis_client.get(f"url:{short_code}")


async def set_cached_url(short_code: str, original_url: str) -> None:
    """Cache a short_code -> original_url mapping."""
    await redis_client.set(f"url:{short_code}", original_url, ex=CACHE_TTL)


async def delete_cached_url(short_code: str) -> None:
    """Remove a short_code from cache."""
    await redis_client.delete(f"url:{short_code}")


async def check_rate_limit(ip: str, limit: int) -> bool:
    """Atomic rate limit check. Returns True if within limit, False if exceeded."""
    key = f"rate:{ip}"
    current = await redis_client.eval(_RATE_LIMIT_SCRIPT, 1, key, 60)
    return int(current) <= limit
