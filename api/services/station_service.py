from typing import List, Optional, Tuple
from fastapi import HTTPException, status

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)

ALLOWED_STATION_SORT_FIELDS = {
    "avg_availability_rate": "dss.avg_availability_rate",
    "high_demand_hour_count": "dss.high_demand_hour_count",
    "active_hour_count": "dss.active_hour_count",
    "station_id": "dss.station_id",
}


def get_daily_stations_summary(
    summary_date: str,
    region_id: Optional[str] = None,
    demand_category: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    sort_column: Optional[str] = None,
    sort_order: str = "ASC",
) -> Tuple[List[dict], int]:
    """
    Fetch station daily summary list for a target date with optional region & demand_category filter.

    Source: mart.daily_station_summary (and mart.station_demand_ranking)
    """
    where_clauses = ["dss.summary_date = CAST(:summary_date AS DATE)"]
    params = {"summary_date": summary_date, "limit": limit, "offset": offset}

    if region_id:
        where_clauses.append("dss.region_id = :region_id")
        params["region_id"] = region_id

    join_sql = ""
    if demand_category:
        join_sql = """
            JOIN mart.station_demand_ranking sdr
              ON dss.summary_date = sdr.ranking_date
             AND dss.station_id = sdr.station_id
        """
        where_clauses.append("sdr.demand_category = :demand_category")
        params["demand_category"] = demand_category.upper()

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    count_sql = f"""
        SELECT COUNT(*) AS count
        FROM mart.daily_station_summary dss
        {join_sql}
        {where_sql}
    """
    count_row = fetch_one(count_sql, params)
    total_count = count_row["count"] if count_row else 0

    order_by_col = sort_column if sort_column else "dss.station_id"
    data_sql = f"""
        SELECT dss.*
        FROM mart.daily_station_summary dss
        {join_sql}
        {where_sql}
        ORDER BY {order_by_col} {sort_order}
        LIMIT :limit OFFSET :offset
    """
    records = fetch_all(data_sql, params)
    return records, total_count


def get_station_daily_history(
    station_id: str,
    start_date: str,
    end_date: str,
) -> List[dict]:
    """
    Fetch daily summary time series for a single station.

    Source: mart.daily_station_summary
    """
    sql = """
        SELECT *
        FROM mart.daily_station_summary
        WHERE station_id = :station_id
          AND summary_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY summary_date ASC
    """
    records = fetch_all(sql, {"station_id": station_id, "start_date": start_date, "end_date": end_date})
    if not records:
        # Check if station exists at all
        exists = fetch_one("SELECT 1 FROM mart.daily_station_summary WHERE station_id = :station_id LIMIT 1", {"station_id": station_id})
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Station '{station_id}' not found."},
            )
    return records


def get_station_hourly_history(
    station_id: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> Tuple[List[dict], int]:
    """
    Fetch hourly station availability time series for a single station.

    Source: mart.hourly_station_availability
    """
    where_clauses = ["station_id = :station_id"]
    params = {
        "station_id": station_id,
        "limit": limit,
        "offset": offset,
    }

    if start_time:
        where_clauses.append("hour_bucket >= CAST(:start_time AS TIMESTAMP)")
        params["start_time"] = start_time

    if end_time:
        where_clauses.append("hour_bucket <= CAST(:end_time AS TIMESTAMP)")
        params["end_time"] = end_time

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    count_sql = f"""
        SELECT COUNT(*) AS count
        FROM mart.hourly_station_availability
        {where_sql}
    """
    count_row = fetch_one(count_sql, params)
    total_count = count_row["count"] if count_row else 0

    data_sql = f"""
        SELECT *
        FROM mart.hourly_station_availability
        {where_sql}
        ORDER BY hour_bucket DESC
        LIMIT :limit OFFSET :offset
    """
    records = fetch_all(data_sql, params)
    return records, total_count


def search_stations(q: str, limit: int = 20) -> List[dict]:
    """
    Search station metadata by station_id or station_name.

    Source: staging.stations or mart.daily_station_summary
    """
    query_param = f"%{q.strip()}%"
    params = {"q": query_param, "limit": limit}

    sql_staging = """
        SELECT DISTINCT
            station_id,
            station_name,
            region_id,
            CAST(NULL AS TEXT) AS region_name,
            latitude,
            longitude,
            capacity
        FROM staging.stations
        WHERE station_id ILIKE :q OR station_name ILIKE :q
        LIMIT :limit
    """
    records = fetch_all(sql_staging, params)

    if not records:
        sql_mart = """
            SELECT DISTINCT
                station_id,
                station_name,
                region_id,
                region_name,
                latitude,
                longitude,
                capacity
            FROM mart.daily_station_summary
            WHERE station_id ILIKE :q OR station_name ILIKE :q
            LIMIT :limit
        """
        records = fetch_all(sql_mart, params)

    return records
