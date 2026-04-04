from __future__ import annotations

from redis.asyncio.client import Redis

from config.settings import settings


def get_redis_client() -> Redis:
    """
    Build an async Redis client.
    """
    return Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        encoding="utf-8",
        health_check_interval=30,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )