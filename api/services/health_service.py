import pendulum
from fastapi import HTTPException, status

from api.cache import get_redis_client
from src.common.db import fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def check_api_health() -> dict:
    """
    Check health status of FastAPI service, PostgreSQL database connection, and Redis cache.

    Raises HTTPException 503 if PostgreSQL connection fails.
    """
    checked_at = pendulum.now("UTC").to_iso8601_string()
    db_status = "error"
    redis_status = "unavailable"

    # 1. Check PostgreSQL Database
    try:
        res = fetch_one("SELECT 1 AS alive")
        if res and res.get("alive") == 1:
            db_status = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Database health check failed: {e}",
            },
        ) from e

    # 2. Check Redis
    try:
        r_client = get_redis_client()
        if r_client and r_client.ping():
            redis_status = "ok"
    except Exception as e:
        logger.warning(f"Redis health check ping failed: {e}")
        redis_status = "unavailable"

    return {
        "status": "ok",
        "database": db_status,
        "redis": redis_status,
        "checked_at": checked_at,
    }
