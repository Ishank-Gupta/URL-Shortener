from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/urlshortener"
    redis_url: str = "redis://redis:6379/0"
    base_url: str = "http://localhost:8000"
    short_code_length: int = 6
    rate_limit_per_minute: int = 30

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
