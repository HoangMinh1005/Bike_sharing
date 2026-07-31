from typing import List, Optional
from fastapi import HTTPException, status

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_daily_system_summary(start_date: str, end_date: str) -> List[dict]:
    """
    Fetch daily system summary records between start_date and end_date.

    Source: mart.daily_system_summary
    """
    sql = """
        SELECT *
        FROM mart.daily_system_summary
        WHERE summary_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY summary_date ASC
    """
    return fetch_all(sql, {"start_date": start_date, "end_date": end_date})


def get_latest_system_summary() -> dict:
    """
    Fetch the latest daily system summary record.

    Source: mart.daily_system_summary
    Raises HTTPException 404 if no system summary record exists.
    """
    sql = """
        SELECT *
        FROM mart.daily_system_summary
        ORDER BY summary_date DESC
        LIMIT 1
    """
    row = fetch_one(sql)
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": "No daily system summary data found in mart.",
            },
        )
    return row


def get_hourly_system_summary(
    start_time: Optional[str],
    end_time: Optional[str],
    limit: int = 24,
    offset: int = 0,
) -> tuple[List[dict], int]:
    """
    Fetch hourly mobility and system availability summary records.

    Source: mart.weather_mobility_summary
    Returns tuple of (records_list, total_count).
    """
    where_clauses = []
    params = {"limit": limit, "offset": offset}

    if start_time:
        where_clauses.append("hour_bucket >= CAST(:start_time AS TIMESTAMP)")
        params["start_time"] = start_time

    if end_time:
        where_clauses.append("hour_bucket <= CAST(:end_time AS TIMESTAMP)")
        params["end_time"] = end_time

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    count_sql = f"SELECT COUNT(*) AS count FROM mart.weather_mobility_summary {where_sql}"
    count_row = fetch_one(count_sql, params)
    total_count = count_row["count"] if count_row else 0

    data_sql = f"""
        SELECT *
        FROM mart.weather_mobility_summary
        {where_sql}
        ORDER BY hour_bucket DESC
        LIMIT :limit OFFSET :offset
    """
    records = fetch_all(data_sql, params)
    return records, total_count
