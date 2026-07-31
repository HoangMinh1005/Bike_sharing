import json
import os
from typing import Any, Optional

import redis

from src.common.logger import get_logger

logger = get_logger(__name__)


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_KEY_PREFIX = os.getenv("CACHE_KEY_PREFIX", "bike_api")

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Initialize or return existing Redis client.

    Redis cache is optional. If Redis is unavailable, this function returns None
    and the API should continue without cache.
    """
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    try:
        client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_timeout=0.5,
            socket_connect_timeout=0.5,
        )

        # Validate connection early.
        client.ping()

        _redis_client = client
        logger.info("Redis cache client initialized successfully.")

        return _redis_client

    except Exception as e:
        logger.warning(f"Redis cache is unavailable: {e}")
        _redis_client = None
        return None


def is_cache_available() -> bool:
    """
    Check whether Redis cache is currently available.

    This is useful for API health checks.
    """
    client = get_redis_client()

    if client is None:
        return False

    try:
        client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis cache ping failed: {e}")
        return False


def make_cache_key(prefix: str, **kwargs: Any) -> str:
    """
    Generate deterministic Redis cache key.

    Example:
        make_cache_key(
            "stations_daily",
            summary_date="2026-07-21",
            limit=50,
            offset=0,
        )

    Result:
        bike_api:stations_daily:limit=50:offset=0:summary_date="2026-07-21"
    """
    key_parts = []

    for key, value in sorted(kwargs.items()):
        if value is None:
            continue

        serialized_value = json.dumps(
            value,
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )

        key_parts.append(f"{key}={serialized_value}")

    param_str = ":".join(key_parts)

    if param_str:
        return f"{CACHE_KEY_PREFIX}:{prefix}:{param_str}"

    return f"{CACHE_KEY_PREFIX}:{prefix}"


def get_cache(key: str) -> Optional[Any]:
    """
    Retrieve deserialized JSON cache value from Redis.

    Returns:
        Cached value if found.
        None if cache miss or Redis error occurs.
    """
    client = get_redis_client()

    if client is None:
        return None

    try:
        cached_data = client.get(key)

        if cached_data is None:
            return None

        return json.loads(cached_data)

    except Exception as e:
        logger.warning(f"Redis get_cache error for key '{key}': {e}")
        return None


def set_cache(
    key: str,
    value: Any,
    ttl_seconds: int = 300,
) -> None:
    """
    Store JSON-serialized value into Redis with TTL in seconds.

    Redis errors are ignored gracefully because cache should not make
    the API fail.
    """
    if ttl_seconds <= 0:
        logger.warning(
            f"Skip setting cache for key '{key}' because ttl_seconds={ttl_seconds}."
        )
        return

    client = get_redis_client()

    if client is None:
        return

    try:
        serialized_value = json.dumps(
            value,
            default=str,
            ensure_ascii=False,
        )

        client.setex(
            name=key,
            time=ttl_seconds,
            value=serialized_value,
        )

    except Exception as e:
        logger.warning(f"Redis set_cache error for key '{key}': {e}")