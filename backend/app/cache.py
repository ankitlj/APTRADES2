from __future__ import annotations

from redis import Redis


def create_redis_client(redis_url: str) -> Redis:
    return Redis.from_url(redis_url, decode_responses=True)


def check_redis(redis_url: str | None) -> str:
    if not redis_url:
        return "not_configured"

    try:
        client = create_redis_client(redis_url)
        client.ping()
        client.close()
    except Exception:
        return "offline"

    return "online"
