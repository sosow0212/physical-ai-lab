"""Redis(async) 클라이언트 팩토리."""

import redis.asyncio as redis

from app.core.config import Settings


def create_redis(settings: Settings) -> redis.Redis:
    """설정 기반 Redis 클라이언트 생성 (decode_responses=True로 str 반환)."""
    return redis.from_url(settings.redis_url, decode_responses=True)
