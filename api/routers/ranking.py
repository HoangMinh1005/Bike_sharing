from typing import List, Optional
from fastapi import APIRouter, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import validate_date_param, validate_date_range, validate_demand_category
from api.response import DataResponse, make_data_response
from api.schemas import StationDemandRanking
from api.services.ranking_service import (
    get_station_demand_ranking,
    get_top_demand_stations,
    get_station_ranking_history,
)

router = APIRouter(prefix="/ranking", tags=["Demand Ranking"])


@router.get("/stations", response_model=DataResponse[List[StationDemandRanking]])
def get_ranking_stations(
    ranking_date: str = Query(..., description="Target ranking date (YYYY-MM-DD)"),
    region_id: Optional[str] = Query(None, description="Optional region filter"),
    demand_category: Optional[str] = Query(None, description="Optional demand category (HIGH, MEDIUM, LOW)"),
    top_n: Optional[int] = Query(None, ge=1, le=5000, description="Optional top N stations limit"),
):
    """Lấy danh sách xếp hạng nhu cầu trạm vào một ngày cụ thể."""
    valid_date = validate_date_param(ranking_date, "ranking_date")
    valid_category = validate_demand_category(demand_category)

    cache_key = make_cache_key(
        "ranking:stations",
        date=valid_date,
        region=region_id,
        category=valid_category,
        top_n=top_n,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_station_demand_ranking(
        ranking_date=valid_date,
        region_id=region_id,
        demand_category=valid_category,
        top_n=top_n,
    )
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/stations/top-demand", response_model=DataResponse[List[StationDemandRanking]])
def get_ranking_top_demand(
    ranking_date: str = Query(..., description="Target ranking date (YYYY-MM-DD)"),
    top_n: int = Query(10, ge=1, le=50, description="Top N high-demand stations"),
):
    """Lấy danh sách các trạm có nhu cầu cao nhất (top demand) vào một ngày cụ thể."""
    valid_date = validate_date_param(ranking_date, "ranking_date")

    cache_key = make_cache_key("ranking:top-demand", date=valid_date, top_n=top_n)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_top_demand_stations(ranking_date=valid_date, top_n=top_n)
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/stations/{station_id}", response_model=DataResponse[List[StationDemandRanking]])
def get_station_ranking_trend(
    station_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """Lấy lịch sử xếp hạng nhu cầu qua các ngày của một trạm cụ thể."""
    valid_start, valid_end = validate_date_range(start_date, end_date)

    cache_key = make_cache_key(
        "ranking:station:trend",
        station_id=station_id,
        start_date=valid_start,
        end_date=valid_end,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_station_ranking_history(
        station_id=station_id,
        start_date=valid_start,
        end_date=valid_end,
    )
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)
