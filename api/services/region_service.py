from typing import List, Optional, Tuple
from fastapi import HTTPException, status

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

ALLOWED_REGION_SORT_FIELDS = {
    "avg_availability_rate": "drs.avg_availability_rate",
    "high_demand_station_count": "drs.high_demand_station_count",
    "station_count": "drs.station_count",
    "region_id": "drs.region_id",
}


def get_daily_regions_summary(
    summary_date: str,
    limit: int = 50,
    offset: int = 0,
    sort_column: Optional[str] = None,
    sort_order: str = "ASC",
) -> Tuple[List[dict], int]:
    """
    Fetch region daily summary list for a target date.

    Source: mart.daily_region_summary
    """
    params = {"summary_date": summary_date, "limit": limit, "offset": offset}
    where_sql = "WHERE drs.summary_date = CAST(:summary_date AS DATE)"

    count_sql = f"SELECT COUNT(*) AS count FROM mart.daily_region_summary drs {where_sql}"
    count_row = fetch_one(count_sql, params)
    total_count = count_row["count"] if count_row else 0

    order_by_col = sort_column if sort_column else "drs.region_id"
    data_sql = f"""
        SELECT drs.*
        FROM mart.daily_region_summary drs
        {where_sql}
        ORDER BY {order_by_col} {sort_order}
        LIMIT :limit OFFSET :offset
    """
    records = fetch_all(data_sql, params)
    return records, total_count


def get_region_daily_history(
    region_id: str,
    start_date: str,
    end_date: str,
) -> List[dict]:
    """
    Fetch daily summary time series for a single region.

    Source: mart.daily_region_summary
    """
    sql = """
        SELECT *
        FROM mart.daily_region_summary
        WHERE region_id = :region_id
          AND summary_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY summary_date ASC
    """
    records = fetch_all(sql, {"region_id": region_id, "start_date": start_date, "end_date": end_date})
    if not records:
        exists = fetch_one("SELECT 1 FROM mart.daily_region_summary WHERE region_id = :region_id LIMIT 1", {"region_id": region_id})
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Region '{region_id}' not found."},
            )
    return records


def get_region_stations(
    region_id: str,
    summary_date: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """
    Fetch list of station daily summaries belonging to a region on summary_date.

    Source: mart.daily_station_summary
    """
    params = {
        "region_id": region_id,
        "summary_date": summary_date,
        "limit": limit,
        "offset": offset,
    }
    where_sql = "WHERE region_id = :region_id AND summary_date = CAST(:summary_date AS DATE)"

    count_sql = f"SELECT COUNT(*) AS count FROM mart.daily_station_summary {where_sql}"
    count_row = fetch_one(count_sql, params)
    total_count = count_row["count"] if count_row else 0

    data_sql = f"""
        SELECT *
        FROM mart.daily_station_summary
        {where_sql}
        ORDER BY station_id ASC
        LIMIT :limit OFFSET :offset
    """
    records = fetch_all(data_sql, params)
    return records, total_count
