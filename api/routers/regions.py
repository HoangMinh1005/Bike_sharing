from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import (
    validate_date_param,
    validate_date_range,
    pagination_params,
    validate_sort_params,
)
from api.response import DataResponse, ListResponse, make_data_response, make_list_response
from api.schemas import RegionDailySummary, StationDailySummary
from api.services.region_service import (
    ALLOWED_REGION_SORT_FIELDS,
    get_daily_regions_summary,
    get_region_daily_history,
    get_region_stations,
)

router = APIRouter(prefix="/regions", tags=["Region Marts"])


@router.get("/daily", response_model=ListResponse[RegionDailySummary])
def get_regions_daily(
    summary_date: str = Query(..., description="Target summary date (YYYY-MM-DD)"),
    sort_by: Optional[str] = Query(None, description="Sort field (avg_availability_rate, high_demand_station_count, station_count, region_id)"),
    sort_order: str = Query("asc", description="Sort order (asc, desc)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy danh sách tổng hợp trạm theo khu vực trong ngày."""
    valid_date = validate_date_param(summary_date, "summary_date")
    sort_col, mapped_order = validate_sort_params(sort_by, sort_order, ALLOWED_REGION_SORT_FIELDS)
    limit, offset = pagination

    cache_key = make_cache_key(
        "regions:daily",
        date=valid_date,
        sort=sort_col,
        order=mapped_order,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_daily_regions_summary(
        summary_date=valid_date,
        limit=limit,
        offset=offset,
        sort_column=sort_col,
        sort_order=mapped_order,
    )

    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=300)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)


@router.get("/{region_id}/daily", response_model=DataResponse[List[RegionDailySummary]])
def get_region_daily(
    region_id: str,
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """Lấy chuỗi thời gian tổng hợp ngày của một khu vực cụ thể."""
    valid_start, valid_end = validate_date_range(start_date, end_date)

    cache_key = make_cache_key(
        "regions:detail:daily",
        region_id=region_id,
        start_date=valid_start,
        end_date=valid_end,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_region_daily_history(region_id=region_id, start_date=valid_start, end_date=valid_end)
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/{region_id}/stations", response_model=ListResponse[StationDailySummary])
def get_region_stations_endpoint(
    region_id: str,
    summary_date: str = Query(..., description="Target summary date (YYYY-MM-DD)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy danh sách các trạm thuộc một khu vực cụ thể vào ngày chỉ định."""
    valid_date = validate_date_param(summary_date, "summary_date")
    limit, offset = pagination

    cache_key = make_cache_key(
        "regions:detail:stations",
        region_id=region_id,
        summary_date=valid_date,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_region_stations(
        region_id=region_id,
        summary_date=valid_date,
        limit=limit,
        offset=offset,
    )
    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=300)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)
