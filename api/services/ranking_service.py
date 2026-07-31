from typing import List, Optional
from fastapi import HTTPException, status

from src.common.db import fetch_all, fetch_one
from src.common.logger import get_logger

logger = get_logger(__name__)


def get_station_demand_ranking(
    ranking_date: str,
    region_id: Optional[str] = None,
    demand_category: Optional[str] = None,
    top_n: int = 20,
) -> List[dict]:
    """
    Fetch station demand ranking for a target ranking date.

    Source: mart.station_demand_ranking
    """
    where_clauses = ["ranking_date = CAST(:ranking_date AS DATE)"]
    params = {"ranking_date": ranking_date, "top_n": top_n}

    if region_id:
        where_clauses.append("region_id = :region_id")
        params["region_id"] = region_id

    if demand_category:
        where_clauses.append("demand_category = :demand_category")
        params["demand_category"] = demand_category.upper()

    where_sql = f"WHERE {' AND '.join(where_clauses)}"

    sql = f"""
        SELECT *
        FROM mart.station_demand_ranking
        {where_sql}
        ORDER BY demand_rank ASC
        LIMIT :top_n
    """
    return fetch_all(sql, params)


def get_top_demand_stations(
    ranking_date: str,
    top_n: int = 10,
) -> List[dict]:
    """
    Shortcut endpoint for top demand stations ordered by demand_rank ASC.

    Source: mart.station_demand_ranking
    """
    sql = """
        SELECT *
        FROM mart.station_demand_ranking
        WHERE ranking_date = CAST(:ranking_date AS DATE)
        ORDER BY demand_rank ASC
        LIMIT :top_n
    """
    return fetch_all(sql, {"ranking_date": ranking_date, "top_n": top_n})


def get_station_ranking_history(
    station_id: str,
    start_date: str,
    end_date: str,
) -> List[dict]:
    """
    Fetch historical demand ranking trend for a single station.

    Source: mart.station_demand_ranking
    """
    sql = """
        SELECT *
        FROM mart.station_demand_ranking
        WHERE station_id = :station_id
          AND ranking_date BETWEEN CAST(:start_date AS DATE) AND CAST(:end_date AS DATE)
        ORDER BY ranking_date ASC
    """
    records = fetch_all(sql, {"station_id": station_id, "start_date": start_date, "end_date": end_date})
    if not records:
        exists = fetch_one(
            "SELECT 1 FROM mart.station_demand_ranking WHERE station_id = :station_id LIMIT 1",
            {"station_id": station_id},
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "NOT_FOUND", "message": f"Station '{station_id}' not found in rankings."},
            )
    return records
