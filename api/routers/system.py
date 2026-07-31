from typing import List, Optional
from fastapi import APIRouter, Depends, Query

from api.cache import get_cache, set_cache, make_cache_key
from api.dependencies import validate_date_range, validate_datetime_range, pagination_params
from api.response import DataResponse, ListResponse, make_data_response, make_list_response
from api.schemas import SystemDailySummary, HourlyMobilitySummary
from api.services.system_service import (
    get_daily_system_summary,
    get_latest_system_summary,
    get_hourly_system_summary,
)

router = APIRouter(prefix="/system", tags=["System Marts"])


@router.get("/daily", response_model=DataResponse[List[SystemDailySummary]])
def get_system_daily(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
):
    """Lấy danh sách tổng hợp hoạt động toàn hệ thống theo ngày."""
    valid_start, valid_end = validate_date_range(start_date, end_date)

    cache_key = make_cache_key("system:daily", start_date=valid_start, end_date=valid_end)
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    records = get_daily_system_summary(valid_start, valid_end)
    set_cache(cache_key, records, ttl_seconds=300)
    return make_data_response(records)


@router.get("/latest", response_model=DataResponse[SystemDailySummary])
def get_system_latest():
    """Lấy tổng hợp hoạt động toàn hệ thống của ngày gần nhất."""
    cache_key = make_cache_key("system:latest")
    cached = get_cache(cache_key)
    if cached is not None:
        return make_data_response(cached)

    record = get_latest_system_summary()
    set_cache(cache_key, record, ttl_seconds=300)
    return make_data_response(record)


@router.get("/hourly", response_model=ListResponse[HourlyMobilitySummary])
def get_system_hourly(
    start_time: Optional[str] = Query(None, description="Start ISO datetime filter (YYYY-MM-DDTHH:MM:SS)"),
    end_time: Optional[str] = Query(None, description="End ISO datetime filter (YYYY-MM-DDTHH:MM:SS)"),
    pagination: tuple[int, int] = Depends(pagination_params),
):
    """Lấy danh sách tổng hợp vận hành và thời tiết toàn hệ thống theo giờ."""
    valid_start, valid_end = validate_datetime_range(start_time, end_time)
    limit, offset = pagination

    cache_key = make_cache_key(
        "system:hourly",
        start_time=valid_start,
        end_time=valid_end,
        limit=limit,
        offset=offset,
    )
    cached = get_cache(cache_key)
    if cached is not None:
        return make_list_response(cached["data"], count=cached["count"], limit=limit, offset=offset)

    records, total_count = get_hourly_system_summary(
        start_time=valid_start,
        end_time=valid_end,
        limit=limit,
        offset=offset,
    )
    set_cache(cache_key, {"data": records, "count": total_count}, ttl_seconds=300)
    return make_list_response(records, count=total_count, limit=limit, offset=offset)
