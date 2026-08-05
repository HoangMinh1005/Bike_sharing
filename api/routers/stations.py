from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import (
    validate_date_param,
    validate_date_range,
    validate_datetime_range,
    validate_demand_category,
    pagination_params,
    validate_sort_params,
)
from api.response import DataResponse, ListResponse, make_data_response, make_list_response
from api.schemas import StationDailySummary, StationHourlyAvailability, StationMetadata
from api.services.station_service import (
    ALLOWED_STATION_SORT_FIELDS,
    get_daily_stations_summary,
    get_station_daily_history,
    get_station_hourly_history,
    search_stations,
)

router = APIRouter(prefix="/stations", tags=["Station Marts"])


@router.get("/daily", response_model=ListResponse[StationDailySummary])
def get_stations_daily(
    summary_date: str = Query(..., description="Target summary date (YYYY-MM-DD)"),
    region_id: Optional[str] = Query(None, description="Optional region ID filter"),
    demand_category: Optional[str] = Query(None, description="Optional demand category (HIGH, MEDIUM, LOW)"),
    sort_by: Optional[str] = Query(None, description="Sort field (avg_availability_rate, high_demand_hour_count, active_hour_count, station_id)"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy danh sách tổng hợp trạm theo ngày có phân trang và lọc."""
    valid_date = validate_date_param(summary_date, "summary_date")
    valid_category = validate_demand_category(demand_category)
    sort_col, mapped_order = validate_sort_params(sort_by, sort_order, ALLOWED_STATION_SORT_FIELDS)
    limit, offset = pagination

    cache_key = make_cache_key(
        "stations:daily",
        date=valid_date,
        region=region_id,
        category=valid_category,
        sort=sort_col,
        order=mapped_order,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_daily_stations_summary(
        summary_date=valid_date,
        region_id=region_id,
        demand_category=valid_category,
        limit=limit,
        offset=offset,
        sort_column=sort_col,
        sort_order=mapped_order,
    )

    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=300)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)


@router.get("/search", response_model=DataResponse[List[StationMetadata]])
def search_stations_endpoint(
    q: str = Query(..., min_length=1, description="Search query string for station ID or name"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
):
    """Tìm kiếm trạm theo ID hoặc tên trạm."""
    cache_key = make_cache_key("stations:search", q=q.strip().lower(), limit=limit)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = search_stations(q=q, limit=limit)
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/{station_id}/daily", response_model=DataResponse[List[StationDailySummary]])
def get_station_daily(
    station_id: str,
    start_date: Optional[str] = Query(None, description="Optional start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Optional end date (YYYY-MM-DD)"),
):
    """Lấy chuỗi thời gian tổng hợp ngày của một trạm cụ thể."""
    import pendulum

    eff_end = end_date or pendulum.now("UTC").to_date_string()
    eff_start = start_date or pendulum.now("UTC").subtract(days=30).to_date_string()

    valid_start, valid_end = validate_date_range(eff_start, eff_end)

    cache_key = make_cache_key(
        "stations:detail:daily",
        station_id=station_id,
        start_date=valid_start,
        end_date=valid_end,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_station_daily_history(station_id=station_id, start_date=valid_start, end_date=valid_end)
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/{station_id}/hourly", response_model=ListResponse[StationHourlyAvailability])
def get_station_hourly(
    station_id: str,
    start_time: Optional[str] = Query(None, description="Optional start ISO datetime filter (YYYY-MM-DDTHH:MM:SS)"),
    end_time: Optional[str] = Query(None, description="Optional end ISO datetime filter (YYYY-MM-DDTHH:MM:SS)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy chuỗi thời gian trạng thái trạm theo giờ của một trạm cụ thể."""
    import pendulum

    eff_end = end_time or pendulum.now("UTC").to_iso8601_string()
    eff_start = start_time or pendulum.now("UTC").subtract(hours=24).to_iso8601_string()

    valid_start, valid_end = validate_datetime_range(eff_start, eff_end)
    limit, offset = pagination

    cache_key = make_cache_key(
        "stations:detail:hourly",
        station_id=station_id,
        start_time=valid_start,
        end_time=valid_end,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_station_hourly_history(
        station_id=station_id,
        start_time=valid_start,
        end_time=valid_end,
        limit=limit,
        offset=offset,
    )
    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=300)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)
